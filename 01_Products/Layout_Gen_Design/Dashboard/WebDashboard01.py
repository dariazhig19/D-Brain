"""Streamlit dashboard — Phase 06 layout + road/rack sketch.

Run with:
    streamlit run 01_Products/Layout_Gen_Design/Dashboard/WebDashboard01.py
"""

import streamlit as st
import sys, os, random, time, threading, traceback
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

import importlib
import Core.Groups, Core.Grid, Core.Pathfind, Core.Stage01
import Core.Plot, Core.CADImport, Core.Rules, Core.Exporter
importlib.reload(Core.Grid)
importlib.reload(Core.Pathfind)
importlib.reload(Core.Groups)
importlib.reload(Core.Stage01)
importlib.reload(Core.Plot)
importlib.reload(Core.CADImport)
importlib.reload(Core.Rules)
importlib.reload(Core.Exporter)

Plot = Core.Plot.Plot
SHAPES = Core.Groups.SHAPES
generate_sketch = Core.Stage01.generate_sketch
CELL_SIZE = Core.Stage01.CELL_SIZE
ROAD_BUFFER = Core.Stage01.ROAD_BUFFER
evaluate_all_v2 = Core.Rules.evaluate_all_v2
export_to_dxf = Core.Exporter.export_to_dxf

@st.cache_data
def cached_load_plot_dxf(path, mtime):
    return Core.CADImport.load_plot_dxf(path)

def draw_orthogonal_line(ax, p1, p2, width, color, alpha=0.95, zorder=1.5, label="", cap_p1=True, cap_p2=True):
    x1, y1 = p1
    x2, y2 = p2
    r = width / 2
    # Draw endpoint caps only if they are not free ends
    if cap_p1:
        ax.add_patch(mpatches.Circle((x1, y1), r, facecolor=color, edgecolor='none', alpha=alpha, zorder=zorder))
    if cap_p2:
        ax.add_patch(mpatches.Circle((x2, y2), r, facecolor=color, edgecolor='none', alpha=alpha, zorder=zorder))
    if abs(y1 - y2) < 0.1: # Horizontal
        xmin = min(x1, x2)
        xmax = max(x1, x2)
        rect = mpatches.Rectangle((xmin, y1 - r), xmax - xmin, width, 
                                  facecolor=color, edgecolor='none', alpha=alpha, zorder=zorder, label=label)
        ax.add_patch(rect)
    elif abs(x1 - x2) < 0.1: # Vertical
        ymin = min(y1, y2)
        ymax = max(y1, y2)
        rect = mpatches.Rectangle((x1 - r, ymin), width, ymax - ymin, 
                                  facecolor=color, edgecolor='none', alpha=alpha, zorder=zorder, label=label)
        ax.add_patch(rect)
    else:
        ax.plot([x1, x2], [y1, y2], color=color, linewidth=width, alpha=alpha, zorder=zorder, label=label)

def draw_fillet(ax, B, u1, u2, r, R, color, alpha=0.95, zorder=1.5, bg_color='#f0f8ff'):
    # I = B - r * u1 + r * u2
    Ix = B[0] - r * u1[0] + r * u2[0]
    Iy = B[1] - r * u1[1] + r * u2[1]
    
    # Tangent points for inner arc
    t1x = Ix - R * u1[0]
    t1y = Iy - R * u1[1]
    t2x = Ix + R * u2[0]
    t2y = Iy + R * u2[1]
    
    # Center of arc
    cx = Ix - R * u1[0] + R * u2[0]
    cy = Iy - R * u1[1] + R * u2[1]
    
    import math
    # Compute angles of T1 and T2 relative to C
    theta1 = math.atan2(t1y - cy, t1x - cx)
    theta2 = math.atan2(t2y - cy, t2x - cx)
    
    # Determine the step direction
    diff = theta2 - theta1
    if diff > math.pi: diff -= 2 * math.pi
    elif diff < -math.pi: diff += 2 * math.pi
    
    # Generate points along the inner arc
    num_pts = 16
    pts_in = [(Ix, Iy)]
    for i in range(num_pts + 1):
        t = theta1 + diff * (i / num_pts)
        pts_in.append((cx + R * math.cos(t), cy + R * math.sin(t)))
        
    # Draw inner fillet (road color)
    polygon_in = mpatches.Polygon(pts_in, facecolor=color, edgecolor='none', alpha=alpha, zorder=zorder)
    ax.add_patch(polygon_in)


def draw_road_with_fillets(ax, path, width, color, fillet_radius=14.0, alpha=0.95, zorder=1.5, label="", is_closed=False, free_ends=None):
    if not path or len(path) < 2:
        return
        
    def pt_key(p):
        return (round(p[0], 3), round(p[1], 3))
        
    if is_closed and len(path) > 2 and pt_key(path[0]) == pt_key(path[-1]):
        path = list(path)[:-1]
        
    # Draw all segments
    for i in range(len(path) - 1):
        p1, p2 = path[i], path[i+1]
        k1, k2 = pt_key(p1), pt_key(p2)
        
        cap_p1 = True
        cap_p2 = True
        
        if free_ends is not None:
            if k1 in free_ends:
                cap_p1 = False
            if k2 in free_ends:
                cap_p2 = False
        else:
            if not is_closed:
                if i == 0:
                    cap_p1 = False
                if i == len(path) - 2:
                    cap_p2 = False
                    
        draw_orthogonal_line(ax, p1, p2, width, color, alpha, zorder, 
                             label if (i == 0 and label) else "", cap_p1=cap_p1, cap_p2=cap_p2)
                             
    if is_closed:
        p_last, p_first = path[-1], path[0]
        k_last, k_first = pt_key(p_last), pt_key(p_first)
        cap_p1 = True
        cap_p2 = True
        if free_ends is not None:
            if k_last in free_ends: cap_p1 = False
            if k_first in free_ends: cap_p2 = False
        draw_orthogonal_line(ax, p_last, p_first, width, color, alpha, zorder, cap_p1=cap_p1, cap_p2=cap_p2)
        
    # Now draw fillets at turns
    import math
    r = width / 2
    
    # Build list of points to process turns
    if is_closed:
        # Loop closed, so pad start with last element and end with first two elements
        padded = [path[-1]] + list(path) + [path[0], path[1]]
    else:
        padded = list(path)
        
    for i in range(1, len(padded) - 1):
        p_prev = padded[i-1]
        p_curr = padded[i]
        p_next = padded[i+1]
        
        # Calculate unit vectors
        v1 = (p_curr[0] - p_prev[0], p_curr[1] - p_prev[1])
        len1 = math.hypot(*v1)
        if len1 < 0.1: continue
        u1 = (v1[0] / len1, v1[1] / len1)
        
        v2 = (p_next[0] - p_curr[0], p_next[1] - p_curr[1])
        len2 = math.hypot(*v2)
        if len2 < 0.1: continue
        u2 = (v2[0] / len2, v2[1] / len2)
        
        # Check if it's a 90 degree turn (cross product close to 1 or -1)
        cross = u1[0]*u2[1] - u1[1]*u2[0]
        if abs(abs(cross) - 1.0) < 0.1:
            R = min(fillet_radius, len1 / 2, len2 / 2)
            if R < 0.5: continue
            draw_fillet(ax, p_curr, u1, u2, r, R, color, alpha, zorder)

def draw_network_with_fillets(ax, segments, width, color, fillet_radius=5.0, alpha=0.95, zorder=1.5, label=""):
    if not segments:
        return
        
    import collections
    adj = collections.defaultdict(list)
    
    def pt_key(p):
        return (round(p[0], 3), round(p[1], 3))
        
    key_to_pt = {}
    
    for seg in segments:
        if not seg or len(seg) < 2:
            continue
        p1, p2 = seg[0], seg[1]
        k1, k2 = pt_key(p1), pt_key(p2)
        if k1 == k2:
            continue
        adj[k1].append(k2)
        adj[k2].append(k1)
        key_to_pt[k1] = p1
        key_to_pt[k2] = p2
        
    # Find all free ends (degree 1 in the network)
    free_ends = {k for k, neighbors in adj.items() if len(neighbors) == 1}
    
    visited_edges = set()
    
    def make_edge(k1, k2):
        return frozenset({k1, k2})
        
    paths = []
    
    # 1. Trace from nodes with degree != 2
    for start_key in list(adj.keys()):
        deg = len(adj[start_key])
        if deg == 2:
            continue
        for nbr_key in adj[start_key]:
            edge = make_edge(start_key, nbr_key)
            if edge in visited_edges:
                continue
            path = [start_key, nbr_key]
            visited_edges.add(edge)
            
            curr = nbr_key
            prev = start_key
            while len(adj[curr]) == 2:
                nbrs = adj[curr]
                next_key = nbrs[0] if nbrs[1] == prev else nbrs[1]
                next_edge = make_edge(curr, next_key)
                if next_edge in visited_edges:
                    break
                path.append(next_key)
                visited_edges.add(next_edge)
                prev = curr
                curr = next_key
            paths.append([key_to_pt[k] for k in path])
            
    # 2. Trace remaining closed loops
    for start_key in list(adj.keys()):
        for nbr_key in adj[start_key]:
            edge = make_edge(start_key, nbr_key)
            if edge in visited_edges:
                continue
            path = [start_key, nbr_key]
            visited_edges.add(edge)
            curr = nbr_key
            prev = start_key
            while len(adj[curr]) == 2:
                nbrs = adj[curr]
                next_key = nbrs[0] if nbrs[1] == prev else nbrs[1]
                next_edge = make_edge(curr, next_key)
                if next_edge in visited_edges:
                    break
                path.append(next_key)
                visited_edges.add(next_edge)
                prev = curr
                curr = next_key
            paths.append([key_to_pt[k] for k in path])
            
    # Draw all traced paths
    for i, path in enumerate(paths):
        is_closed = (len(path) > 2 and pt_key(path[0]) == pt_key(path[-1]))
        if is_closed:
            path = path[:-1]
        draw_road_with_fillets(ax, path, width, color, fillet_radius, alpha, zorder, 
                               label if (i == 0 and label) else "", is_closed=is_closed, free_ends=free_ends)

def draw_network_squared(ax, segments, width, color, alpha=0.95, zorder=3.5, label=""):
    if not segments:
        return
        
    import collections
    import math
    
    adj = collections.defaultdict(list)
    
    def pt_key(p):
        return (round(p[0], 3), round(p[1], 3))
        
    for seg in segments:
        if not seg or len(seg) < 2:
            continue
        p1, p2 = seg[0], seg[1]
        k1, k2 = pt_key(p1), pt_key(p2)
        if k1 == k2:
            continue
        adj[k1].append(k2)
        adj[k2].append(k1)
        
    r = width / 2
    
    for i, seg in enumerate(segments):
        if not seg or len(seg) < 2:
            continue
        p1, p2 = list(seg[0]), list(seg[1])
        k1, k2 = pt_key(p1), pt_key(p2)
        
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        L = math.hypot(dx, dy)
        if L < 0.1:
            continue
            
        ux = dx / L
        uy = dy / L
        
        ext = min(r, L / 2)
        
        # Extend p1 if it is connected to other segments
        if len(adj[k1]) > 1:
            p1[0] -= ext * ux
            p1[1] -= ext * uy
            
        # Extend p2 if it is connected to other segments
        if len(adj[k2]) > 1:
            p2[0] += ext * ux
            p2[1] += ext * uy
            
        draw_orthogonal_line(ax, p1, p2, width, color, alpha, zorder, 
                             label if (i == 0 and label) else "", cap_p1=False, cap_p2=False)



plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

st.set_page_config(page_title="Roads Test", layout="wide")

# ── Shared sidebar: plot input ─────────────────────────────────────────────
# Phase 06 polygon migration: the plot, gate, boom barrier and fixed anchors are
# DRAWN in CAD and imported from a DXF (layers: Plot / Gate / Gate House /
# RAW Tank / GIS / Gate House Boom Barrier). The ONLY engine input that stays a
# UI control is the wind direction. The legacy rectangle + placement sliders are
# kept solely as a no-DXF fallback inside a collapsed expander.
st.sidebar.header("Site")
wind_dir = st.sidebar.selectbox("Wind Direction",
                                ["North", "South", "East", "West"], index=2)

# Plot input: read a DXF straight from disk (browser upload is blocked here by
# security policy). Default candidates are searched in order; the first that
# exists is offered. You can also type any absolute path.
_PROJ_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_REPO_DIR = os.path.abspath(os.path.join(_PROJ_DIR, "..", ".."))
_DXF_CANDIDATES = [
    os.path.join(_PROJ_DIR, "Data", "Plot.dxf"),
    os.path.join(_PROJ_DIR, "Data", "sample_plot.dxf"),
    os.path.join(_REPO_DIR, "Plot.dxf"),
]
_default_dxf = next((p for p in _DXF_CANDIDATES if os.path.exists(p)), _DXF_CANDIDATES[0])

st.sidebar.caption("Browser upload disabled — reading DXF from disk.")
dxf_path = st.sidebar.text_input("Local DXF/DWG path", value=_default_dxf)
load_dxf = st.sidebar.checkbox("Load plot from this file", value=True)

plot_import = None
if load_dxf and dxf_path:
    if os.path.exists(dxf_path):
        try:
            mtime = os.path.getmtime(dxf_path)
            plot_import = cached_load_plot_dxf(dxf_path, mtime)
            st.session_state["plot_import"] = plot_import
        except Exception as ex:  # noqa: BLE001
            st.sidebar.error(f"Could not read DXF: {ex}")
            plot_import = None
    else:
        st.sidebar.error(f"File not found: {dxf_path}")

if plot_import and plot_import.get("plot_polygon"):
    poly = plot_import["plot_polygon"]
    p = Plot(poly)
    st.sidebar.success(f"DXF loaded — {len(poly)}-sided plot, bbox {p.size[0]:.0f}×{p.size[1]:.0f} m")
    if plot_import.get("warnings"):
        with st.sidebar.expander("DXF warnings"):
            for w in plot_import["warnings"]:
                st.write("• " + w)

# ── Rectangle fallback (only used when no DXF is uploaded) ──────────────────
with st.sidebar.expander("Rectangle fallback (no DXF)", expanded=plot_import is None):
    site_width  = st.slider("Plot Width (A)",  100, 1000, 500, step=10)
    site_length = st.slider("Plot Length (B)", 100, 1000, 270, step=10)
    gate_side  = st.selectbox("Gate edge", ["N", "S", "E", "W"], index=0)
    gate_ratio = st.slider("Gate position along edge", 0.1, 0.9, 0.4, step=0.05)
    gh_edge   = st.selectbox("Edge (GH)",     ["N", "S", "E", "W"], index=0)
    gh_ratio  = st.slider("Position (GH)",    0.0, 1.0, 0.6, step=0.05)
    gh_offset = st.slider("Offset (GH)",      0, 50, 15, step=1)
    bb_edge   = st.selectbox("Boom Barrier Side (GH)", ["N", "S", "E", "W"], index=0)
    gis_edge   = st.selectbox("Edge (GIS)",   ["N", "S", "E", "W"], index=0)
    gis_ratio  = st.slider("Position (GIS)",  0.0, 1.0, 0.9, step=0.05)
    gis_offset = st.slider("Offset (GIS)",    0, 50, 15, step=1)
    water_edge   = st.selectbox("Edge (RAW Water)", ["N", "S", "E", "W"], index=2)
    water_ratio  = st.slider("Position (RAW Water)", 0.0, 1.0, 0.2, step=0.05)
    water_offset = st.slider("Offset (RAW Water)",   0, 50, 0, step=1)

st.sidebar.divider()

if True:  # Phase 06 — Sketch roads
    st.title("Phase 06 — Block + Road Sketch")
    st.markdown("Reference: [Phase 06 Plan](file:///x:/CST%EB%B3%B8%EB%B6%80%20%28%EA%B5%AC%20%EA%B8%B0%EC%88%A0%EC%A7%80%EC%9B%90%EB%B6%80%20%ED%8F%B4%EB%8D%94%29/15.%20%EB%8B%A4%EB%A6%AC%EC%95%84/D-Brain/00_Input/Phase_06_Plan.md)")
    st.caption("Steps 1.1–1.5: blocks · ring road + spurs · rack network")

    st.sidebar.header("Phase 06 Settings")
    show_grid     = st.sidebar.checkbox("§2 — 2m Grid", value=False)
    show_buffer       = st.sidebar.checkbox(f"§3.5.B — Block buffers ({ROAD_BUFFER}m / 16m)", value=False)
    show_rack_no_rack = st.sidebar.checkbox("§3.6.A — Rack baseline (no-rack: 8m / 16m)", value=False)
    show_rack_w_rack  = st.sidebar.checkbox("§3.6.A — Rack w-rack (8m / 16m / 24m / 30m)", value=False)
    show_a1_ring      = st.sidebar.checkbox("§3.4 — Ring Road + Spurs", value=True)
    show_rack_b1      = st.sidebar.checkbox("§3.6.B — Rack spines", value=True)
    show_spine_debug  = st.sidebar.checkbox("Show Spine Debug Visualizer", value=False)
    show_before_recenter = st.sidebar.checkbox("§3.8 — Plot + gate before recenter", value=False)
    show_legend   = st.sidebar.checkbox("Legend", value=False)
    fix_seed      = st.sidebar.checkbox("Fix seed", value=True)
    seed_val      = st.sidebar.number_input("Seed", 0, 10000, 42, disabled=not fix_seed)

    # Single generate button. With a DXF loaded it generates ONE layout on the
    # real plot polygon (current migration version, blocks only). Without a DXF
    # it falls back to the legacy full rectangle sketch.
    _has_poly = bool(plot_import and plot_import.get("plot_polygon"))
    N_LAYOUTS = st.sidebar.number_input("Layouts to generate", 1, 30, 10)
    gen_timeout = st.sidebar.number_input("Per-layout timeout (s)", 5, 300, 40,
                                          help="If one layout takes longer than this it is skipped and flagged — catches a hung/looping seed.")
    if st.button("Generate Layouts", type="primary", use_container_width=True):
        sketches = []
        gen_log = []
        if _has_poly:
            p = Plot(plot_import["plot_polygon"])
            params = p.size

            # Run ONE generate_sketch in a worker thread so a hung/looping seed
            # can be skipped via a join-timeout (the synchronous call would
            # otherwise freeze the whole app — this is the "stopped at 9" bug).
            # The worker calls NO st.* functions, so it's Streamlit-safe.
            def _gen_one(seed):
                holder = {}
                def _w():
                    try:
                        if fix_seed and seed is not None:
                            random.seed(seed)
                        holder["s"] = generate_sketch(
                            p.size[0], p.size[1], wind_dir,
                            plot=p,
                            dxf_anchors=plot_import.get("anchors") or {},
                            dxf_gate=plot_import.get("gate_point"),
                            dxf_boom=plot_import.get("boom_barrier"),
                            blocks_only=True,
                        )
                    except Exception:
                        holder["err"] = traceback.format_exc()
                th = threading.Thread(target=_w, daemon=True)
                th.start()
                th.join(int(gen_timeout))
                return holder, th.is_alive()

            prog = st.progress(0.0, text=f"Generating {N_LAYOUTS} layouts…")
            status = st.empty()
            log_box = st.empty()
            for i in range(int(N_LAYOUTS)):
                # Vary the seed per layout so each is distinct yet reproducible
                # when "Fix seed" is on; otherwise rely on the engine's jitter.
                seed = int(seed_val) + i if fix_seed else None
                status.info(f"▶ Layout {i+1}/{int(N_LAYOUTS)} (seed={seed}) — generating…")
                t0 = time.time()
                holder, timed_out = _gen_one(seed)
                secs = time.time() - t0
                dbg = getattr(Core.Stage01, "_last_debug", {}) or {}
                if timed_out:
                    gen_log.append(f"#{i+1:>2} ⏱ TIMEOUT >{int(gen_timeout)}s (seed={seed}) — hung/looping seed, skipped")
                elif "err" in holder:
                    last = holder["err"].strip().splitlines()[-1]
                    gen_log.append(f"#{i+1:>2} ✗ ERROR (seed={seed}, {secs:.1f}s): {last}")
                elif holder.get("s") is None:
                    reason = ("⏱ engine time-budget exceeded" if dbg.get("timed_out")
                              else f"failed_at={dbg.get('failed_at','?')}")
                    gen_log.append(f"#{i+1:>2} ✗ no-fit (seed={seed}, {secs:.1f}s, "
                                   f"attempts={dbg.get('total_attempts','?')}, {reason})")
                else:
                    sketches.append(holder["s"])
                    gen_log.append(f"#{i+1:>2} ✓ ok (seed={seed}, {secs:.1f}s, {len(holder['s']['blocks'])} blocks)")
                prog.progress((i + 1) / int(N_LAYOUTS), text=f"Generating layouts… {i+1}/{int(N_LAYOUTS)}")
                log_box.code("\n".join(gen_log), language="text")
            prog.empty(); status.empty()
        else:
            if fix_seed:
                random.seed(int(seed_val))
            with st.spinner("Generating layout…"):
                s = generate_sketch(  # → §3.1 (legacy rectangle fallback)
                    site_width, site_length, wind_dir,
                    gate_side=gate_side, gate_ratio=gate_ratio,
                    gh_edge=gh_edge,    gh_ratio=gh_ratio,    gh_offset=gh_offset,
                    bb_edge=bb_edge,
                    gis_edge=gis_edge,  gis_ratio=gis_ratio,  gis_offset=gis_offset,
                    water_edge=water_edge, water_ratio=water_ratio, water_offset=water_offset,
                )
            params = (site_width, site_length)
            if s is not None:
                sketches = [s]
        st.session_state["gen_log06"] = gen_log
        if not sketches:
            st.error("No layout placed — see the generation log below for timeouts/failures.")
            st.session_state["sketches06"] = None
            st.session_state["sketch06"] = None
        else:
            st.session_state["sketches06"] = sketches
            st.session_state["sketch06"] = sketches[0]
            st.session_state["params06"] = params

    sketch = st.session_state.get("sketch06")

    # Generation debugger — per-layout timing / timeouts / failures.
    _gen_log = st.session_state.get("gen_log06")
    if _gen_log:
        n_ok = sum(1 for ln in _gen_log if "✓" in ln)
        n_to = sum(1 for ln in _gen_log if "TIMEOUT" in ln)
        n_bad = len(_gen_log) - n_ok
        title = f"🔬 Generation log — {n_ok} ok / {n_bad} failed" + (f" ({n_to} timeout)" if n_to else "")
        with st.expander(title, expanded=bool(n_bad)):
            st.code("\n".join(_gen_log), language="text")

    if sketch is None:
        dbg = Core.Stage01._last_debug
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
            ALL_BLOCKS = list(Core.Stage01.BLOCK_FOOTPRINTS.keys())
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
            st.info("Load a plot DXF (or use the rectangle fallback), then click **Generate Layouts**.")
        st.stop()

    # ── Gallery of all generated layouts (thumbnails) ───────────────────────
    # When several layouts were generated, show a compact thumbnail of each and
    # let the user pick one to inspect in full detail (the detailed renderer
    # below draws whichever `sketch` is selected here).
    sketches = st.session_state.get("sketches06") or ([sketch] if sketch else [])
    if len(sketches) > 1 and sketches[0].get("blocks_only"):
        st.markdown(f"### {len(sketches)} layouts · wind {wind_dir}")

        def _thumb(sk):
            poly = sk.get("plot_polygon")
            fig, ax = plt.subplots(figsize=(5.2, 3.4), dpi=90)
            if poly:
                vx = [v[0] for v in poly] + [poly[0][0]]
                vy = [v[1] for v in poly] + [poly[0][1]]
                ax.fill(vx, vy, color="#f0f8ff", zorder=0)
                ax.plot(vx, vy, color="black", lw=1.0, zorder=1)
            draw_network_squared(ax, sk.get("rack_segments") or [], width=6, color='#d35400', zorder=3)
            for b in sk["blocks"]:
                bcx, bcy = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
                if b["name"] in ("RAW Water Tank", "Flare"):
                    ax.add_patch(mpatches.Circle((bcx, bcy), min(b["width"], b["height"]) / 2,
                                                 facecolor=b["color"], edgecolor='black', alpha=0.85, zorder=2))
                else:
                    ax.add_patch(mpatches.Rectangle((b["x"], b["y"]), b["width"], b["height"],
                                                    facecolor=b["color"], edgecolor='black', alpha=0.85, zorder=2))
            # Draw road on previews
            ring_road = sk.get("ring_road")
            if ring_road:
                draw_road_with_fillets(ax, ring_road, width=8, color='#7f8c8d',
                                       fillet_radius=14.0, alpha=0.95, zorder=1.5, is_closed=True)
            gs = sk.get("gate_spur") or []
            rs = sk.get("ring_spur") or []
            if gs and rs:
                combined_spur = list(rs) + list(gs)[1:]
                draw_road_with_fillets(ax, combined_spur, width=8, color='#7f8c8d',
                                       fillet_radius=14.0, alpha=0.95, zorder=1.5, is_closed=False)
            elif gs:
                draw_road_with_fillets(ax, gs, width=8, color='#7f8c8d',
                                       fillet_radius=14.0, alpha=0.95, zorder=1.5, is_closed=False)

            gpt = sk.get("gate_point")
            if gpt:
                ax.plot(*gpt, "o", color='#c0392b', markersize=6, zorder=3)
            ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_color('#cccccc')
                spine.set_linewidth(0.8)
            return fig

        cols_per_row = 2
        for i in range(0, len(sketches), cols_per_row):
            row = st.columns(cols_per_row)
            for j, col in enumerate(row):
                idx = i + j
                if idx >= len(sketches):
                    break
                with col:
                    st.caption(f"**Layout {idx+1}** · {sketches[idx].get('boundary_pass_label', '')}")
                    f = _thumb(sketches[idx])
                    st.pyplot(f)
                    plt.close(f)

        st.divider()
        pick = st.selectbox("Inspect layout # (full detail below)",
                            list(range(1, len(sketches) + 1)), index=0)
        sketch = sketches[pick - 1]

    # ── Current version renderer (polygon, blocks only) ─────────────────────
    # When the layout was generated on the plot polygon we draw it here and stop;
    # the legacy full-sketch renderer below only runs for the rectangle fallback.
    if sketch.get("blocks_only"):
        poly = sketch.get("plot_polygon")
        blocks = sketch["blocks"]

        # 3-pass boundary tolerance status banner.
        tol_used = sketch.get("boundary_tol_used")
        if tol_used is not None:
            if tol_used < 0:
                st.success(f"🟢 Pass 1 — strict ({abs(tol_used):.0f} m inner margin)")
            elif tol_used == 0:
                st.info("🔵 Pass 2 — inside plot (0 m tolerance)")
            else:
                st.warning(f"🟡 Pass 3 — relaxed (up to {tol_used:.0f} m past the boundary)")

        fig, ax = plt.subplots(figsize=(13, 8), dpi=110)
        # §3.8 Recenter — plot polygon BEFORE recenter, faded dashed (Phase 9).
        poly_before = sketch.get("plot_polygon_before")
        if show_before_recenter and poly_before and poly_before != poly:
            bvx = [v[0] for v in poly_before] + [poly_before[0][0]]
            bvy = [v[1] for v in poly_before] + [poly_before[0][1]]
            ax.plot(bvx, bvy, color='#b0b0b0', lw=1.0, ls='--', alpha=0.7, zorder=0.5,
                    label='Plot (before recenter)')
            gpb = sketch.get("gate_point_before")
            if gpb:
                ax.plot(*gpb, "o", color='#b0b0b0', markersize=7, alpha=0.7, zorder=0.6)
        if poly:
            vx = [v[0] for v in poly] + [poly[0][0]]
            vy = [v[1] for v in poly] + [poly[0][1]]
            ax.fill(vx, vy, color="#f0f8ff", zorder=0)
            ax.plot(vx, vy, color="black", lw=1.2, zorder=1, label="Plot boundary")
            allx = [v[0] for v in poly] + ([v[0] for v in poly_before] if poly_before else [])
            ally = [v[1] for v in poly] + ([v[1] for v in poly_before] if poly_before else [])
            sw_b, sl_b = max(allx), max(ally)
        else:
            sw_b, sl_b = st.session_state.get("params06", (site_width, site_length))

        racks_data = [{"name": "Pipe Rack", "segments": sketch.get("rack_segments", [])}]
        gate_pt = sketch.get("gate_point")
        scoring = evaluate_all_v2(blocks, racks_data, sw_b, sl_b, wind_dir, gate_point=gate_pt, plot=poly)

        if show_grid:
            cs = CELL_SIZE
            for i in range(int(sw_b // cs) + 1):
                ax.axvline(i * cs, color='#dddddd', lw=0.2, zorder=0.1)
            for j in range(int(sl_b // cs) + 1):
                ax.axhline(j * cs, color='#dddddd', lw=0.2, zorder=0.1)

        if show_a1_ring and sketch.get("ring_road"):
            draw_road_with_fillets(ax, sketch["ring_road"], width=8, color='#7f8c8d',
                                   fillet_radius=14.0, alpha=0.95, zorder=1.5,
                                   label='§3.4.A Ring Road', is_closed=True)
        if show_a1_ring:
            # Gate spur + ring spur, joined like the legacy renderer (§3.4.B/D).
            gs = sketch.get("gate_spur") or []
            rs = sketch.get("ring_spur") or []
            if gs and rs:
                combined_spur = list(rs) + list(gs)[1:]
                draw_road_with_fillets(ax, combined_spur, width=8, color='#7f8c8d',
                                       fillet_radius=14.0, alpha=0.95, zorder=1.5,
                                       label='§3.4.B/D Gate & Ring Spur', is_closed=False)
            elif gs:
                draw_road_with_fillets(ax, gs, width=8, color='#7f8c8d',
                                       fillet_radius=14.0, alpha=0.95, zorder=1.5,
                                       label='§3.4.B Gate Road', is_closed=False)

        # Pipe rack network (§3.6) — 6 m orange centerlines.
        if show_rack_b1:
            draw_network_squared(ax, sketch.get("rack_segments", []), width=6, color='#d35400', zorder=3.5,
                                 label='§3.6 Pipe Rack')

        # Spine debug visualizer — raw PB↔CT spine (green) + water cluster (cyan),
        # dashed with endpoint dots, like the legacy renderer.
        if show_spine_debug:
            for i, seg in enumerate(sketch.get("spine_centerlines") or []):
                (x0, y0), (x1, y1) = seg
                ax.plot([x0, x1], [y0, y1], color='#2ecc71', ls='--', lw=2.5, alpha=0.9, zorder=3.8,
                        label='Spine (PB↔CT)' if i == 0 else "")
                ax.plot([x0, x1], [y0, y1], 'o', color='#27ae60', markersize=6, zorder=3.9)
            for i, seg in enumerate(sketch.get("water_cluster_segments") or []):
                (x0, y0), (x1, y1) = seg
                ax.plot([x0, x1], [y0, y1], color='#00d2d3', ls='--', lw=2.5, alpha=0.9, zorder=3.8,
                        label='Water cluster spine' if i == 0 else "")
                ax.plot([x0, x1], [y0, y1], 'o', color='#01a3a4', markersize=6, zorder=3.9)
            # MAIN RACK OUTPUT (step 7c) — the spine portion inside the PB case1
            # buffer, drawn bold purple on top of the green PB↔CT spine.
            mro = sketch.get("main_rack_output")
            if mro:
                (mx0, my0), (mx1, my1) = mro
                ax.plot([mx0, mx1], [my0, my1], color='#8e44ad', ls='-', lw=5.0,
                        solid_capstyle='round', alpha=0.95, zorder=4.0, label='MAIN RACK')
                ax.plot([mx0, mx1], [my0, my1], 'o', color='#6c3483', markersize=6, zorder=4.05)
            # PB↔CT spine × PB case1 rack-buffer intersection (cut point) — magenta star.
            for i, pt in enumerate(sketch.get("pb_buffer_hits") or []):
                ax.plot(pt[0], pt[1], marker='*', color='#e84393', markersize=16,
                        markeredgecolor='black', markeredgewidth=0.8, zorder=4.2,
                        label='Spine × PB buffer (cut)' if i == 0 else "")
            for i, seg in enumerate(sketch.get("pruned_rack_segments") or []):
                (x0, y0), (x1, y1) = seg
                ax.plot([x0, x1], [y0, y1], color='#95a5a6', ls=':', lw=2.0, alpha=0.7, zorder=3.4,
                        label='Pruned rack segments' if i == 0 else "")

        if show_buffer:
            legended_buffers = set()
            for b in blocks:
                is_rack = b["name"] in Core.Stage01.RACK_BLOCKS
                snap_buf = Core.Stage01.ROAD_W_RACK_OFFSET if is_rack else Core.Stage01.ROAD_BUFFER
                color = '#2980b9' if is_rack else '#34495e'
                lbl = f'§3.5.B {snap_buf}m road buffer'
                xs = [b["x"] - snap_buf, b["x"] + b["width"] + snap_buf,
                      b["x"] + b["width"] + snap_buf, b["x"] - snap_buf, b["x"] - snap_buf]
                ys = [b["y"] - snap_buf, b["y"] - snap_buf,
                      b["y"] + b["height"] + snap_buf, b["y"] + b["height"] + snap_buf, b["y"] - snap_buf]
                ax.plot(xs, ys, color=color, linestyle='--', linewidth=1.0, alpha=0.8, zorder=1.8,
                        label=lbl if lbl not in legended_buffers else "")
                legended_buffers.add(lbl)

        # Rack buffers (§3.6.A) — the Case 1 (6 m) / Case 2 (22 m) rack-buffer
        # rectangles. The MAIN RACK is cut against the PB Case 1 buffer (step 7c),
        # so showing these makes the cut point easy to verify. The ACTIVE case is
        # drawn solid/bold; the inactive case faded.
        if show_rack_w_rack and sketch.get("rack_buffers"):
            rack_buffers = sketch["rack_buffers"]
            active_cases = sketch.get("active_rack_cases") or {}
            legended_rack = set()
            case_style = {
                "case1_rack": ('#00b894', f'Case 1 rack buffer ({Core.Stage01.RACK_CASE1_OFFSET} m)'),
                "case2_rack": ('#8e44ad', f'Case 2 rack buffer ({Core.Stage01.RACK_CASE2_OFFSET} m)'),
            }
            # Standard rack blocks show BOTH cases; these extra blocks show only
            # their Case 1 (8 m) rack buffer.
            case1_only = ("GIS", "Warehouse", "Admin Building", "Flare")
            rack_block_names = list(Core.Stage01.RACK_BLOCKS) if hasattr(Core.Stage01, "RACK_BLOCKS") else list(rack_buffers)
            draw_names = list(dict.fromkeys(list(rack_block_names) + list(case1_only)))
            for name in draw_names:
                cases = rack_buffers.get(name) or {}
                keys = ("case1_rack",) if name in case1_only and name not in rack_block_names else ("case1_rack", "case2_rack")
                for ck in keys:
                    col, lbl = case_style[ck]
                    rect = cases.get(ck)
                    if not rect:
                        continue
                    rx, ry, rw, rh = rect
                    is_active = active_cases.get(name) == ck
                    ax.plot([rx, rx+rw, rx+rw, rx, rx], [ry, ry, ry+rh, ry+rh, ry],
                            color=col, linestyle='-' if is_active else ':',
                            linewidth=1.8 if is_active else 1.0,
                            alpha=0.95 if is_active else 0.55, zorder=1.9,
                            label=lbl if lbl not in legended_rack else "")
                    legended_rack.add(lbl)

        for b in blocks:
            bcx, bcy = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
            if b["name"] in ("RAW Water Tank", "Flare"):
                ax.add_patch(mpatches.Circle((bcx, bcy), min(b["width"], b["height"]) / 2,
                                             facecolor=b["color"], edgecolor='black', alpha=0.85, zorder=2))
            else:
                ax.add_patch(mpatches.Rectangle((b["x"], b["y"]), b["width"], b["height"],
                                                facecolor=b["color"], edgecolor='black', alpha=0.85, zorder=2))
            ax.text(bcx, bcy, b["name"], ha="center", va="center", fontsize=7, zorder=2.5)

        gpt = sketch.get("gate_point")
        if gpt:
            ax.plot(*gpt, "o", color='#c0392b', markersize=10, zorder=3, label='Gate')
        boom = sketch.get("boom_barrier")
        if boom:
            ax.plot([boom[0][0], boom[1][0]], [boom[0][1], boom[1][1]],
                    color='#e67e22', lw=3, zorder=2.5, label='Boom barrier')

        ax.set_aspect("equal")
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color('#cccccc')
            spine.set_linewidth(0.8)
        if show_legend:
            ax.legend(loc="upper right", fontsize=7)
        ax.set_title(f"Layout on {len(poly) if poly else 4}-sided plot · wind {wind_dir}")
        st.pyplot(fig)

        st.dataframe(
            [{"Block": b["name"], "x": round(b["x"], 1), "y": round(b["y"], 1),
              "w": round(b["width"], 1), "h": round(b["height"], 1), "rotated": b.get("rotated", False)}
             for b in blocks],
            use_container_width=True, hide_index=True)

        # ── Detailed Rule Breakdown ─────────────────────────────────────────────
        st.divider()
        st.markdown("#### Detailed Rule Breakdown")
        col_s, col_p, col_f = st.columns(3)
        passing = sum(1 for r in scoring["results"] if r["passed"])
        failing = len(scoring["results"]) - passing
        col_s.metric("Total Penalty Score", f"{scoring['total_penalty']:,.0f} pts")
        col_p.metric("Passing", f"{passing} / {len(scoring['results'])}")
        col_f.metric("Failing", str(failing))

        score_rows = []
        for r in scoring["results"]:
            score_rows.append({
                "Rule ID": r["id"],
                "Rule Name": r["name"],
                "Status": "✅ PASS" if r["passed"] else "❌ FAIL",
                "Measured": r["measured"],
                "Threshold": r["threshold"],
                "Penalty": f"{r['penalty']:,.0f} pts",
                "Calculation": r["calc"]
            })
        st.dataframe(score_rows, use_container_width=True, hide_index=True)

        # ── DXF Export ─────────────────────────────────────────────────────────
        st.divider()
        st.markdown("#### Export to CAD")
        st.caption("Exports the selected layout as a **DXF file** containing all polygon boundaries, building outlines, road centerlines, and labels on separate named layers.")
        _, export_col, _ = st.columns([2, 3, 2])
        with export_col:
            try:
                layout_for_export = {
                    "groups": sketch["blocks"],
                    "racks": racks_data,
                    "scoring": scoring,
                    "ring_road": sketch.get("ring_road"),
                    "gate_spur": sketch.get("gate_spur"),
                    "ring_spur": sketch.get("ring_spur"),
                }
                dxf_stream = export_to_dxf(layout_for_export, sw_b, sl_b, plot=poly)
                filename = f"PowerPlan_Layout_{pick:02d}_{int(scoring['total_penalty'])}pts.dxf"
                st.download_button(
                    label="Download DXF",
                    data=dxf_stream,
                    file_name=filename,
                    mime="application/dxf",
                    use_container_width=True,
                    type="primary",
                )
            except Exception as e:
                st.error(f"DXF export failed: {e}")

        # ── Debug output (copy & send if something looks wrong) ─────────────
        def _fmt_pts(pts, n=0):
            return [(round(x, n), round(y, n)) for x, y in (pts or [])]

        dbg_lines = []
        dbg_lines.append(f"wind = {wind_dir}")
        dbg_lines.append(f"pass = {sketch.get('boundary_pass_label')} (tol {sketch.get('boundary_tol_used')})")
        _rd = sketch.get("recenter_delta")
        if _rd:
            dbg_lines.append(f"recenter_delta = ({round(_rd[0],1)}, {round(_rd[1],1)})")
        if poly:
            dbg_lines.append(f"plot_polygon ({len(poly)} pts) = {_fmt_pts(poly)}")
        dbg_lines.append(f"gate_point = {_fmt_pts([sketch.get('gate_point')]) if sketch.get('gate_point') else None}")
        dbg_lines.append(f"boom_barrier = {_fmt_pts(sketch.get('boom_barrier'))}")
        dbg_lines.append(f"gate_spur ({len(sketch.get('gate_spur') or [])} pts) = {_fmt_pts(sketch.get('gate_spur'))}")
        dbg_lines.append(f"ring_spur ({len(sketch.get('ring_spur') or [])} pts) = {_fmt_pts(sketch.get('ring_spur'))}")
        rr = sketch.get("ring_road") or []
        if rr:
            rxs = [q[0] for q in rr]; rys = [q[1] for q in rr]
            dbg_lines.append(f"ring_road bbox = ({round(min(rxs))},{round(min(rys))})..({round(max(rxs))},{round(max(rys))})")
        wt = sketch.get("water_triangle") or []
        dbg_lines.append(f"water_triangle ({len(wt)} pts) = {_fmt_pts(wt)}")
        wcs = sketch.get("water_cluster_segments") or []
        dbg_lines.append(f"water_cluster_segments = {len(wcs)}")
        for i, seg in enumerate(wcs):
            dbg_lines.append(f"  water[{i}] = {_fmt_pts(seg)}")
        racks = sketch.get("rack_segments") or []
        dbg_lines.append(f"rack_segments = {len(racks)}")
        for i, seg in enumerate(racks):
            dbg_lines.append(f"  rack[{i}] = {_fmt_pts(seg)}")
        dbg_lines.append("blocks:")
        for b in blocks:
            dbg_lines.append(f"  {b['name']:16} x={b['x']:.0f} y={b['y']:.0f} w={b['width']:.0f} h={b['height']:.0f} rot={b.get('rotated', False)}")
        dbg = "\n".join(dbg_lines)
        with st.expander("🐞 Debug output (copy & paste this if you see a bug)", expanded=False):
            st.code(dbg, language="text")
        st.stop()

    sw, sl = st.session_state.get("params06", (site_width, site_length))
    blocks        = sketch["blocks"]
    ring_road     = sketch["ring_road"]
    gate_pt       = sketch["gate_point"]
    pb_center     = sketch["pb_center"]

    fig, ax = plt.subplots(figsize=(13, 8), dpi=110)

    # Plot rectangle — recentered on the content bbox (§3.8 Recenter). Content
    # keeps its coords; only the plot frame (and gate) move.
    px0, py0, pw, ph = sketch.get("plot_bounds", (0, 0, sw, sl))
    px1, py1 = px0 + pw, py0 + ph

    # Plot BEFORE recenter (original frame) — drawn faded/dashed for comparison.
    bx0, by0, bw, bh = sketch.get("plot_bounds_before", (0, 0, sw, sl))
    bx1, by1 = bx0 + bw, by0 + bh
    if show_before_recenter and (bx0, by0) != (px0, py0):
        ax.plot([bx0,bx1,bx1,bx0,bx0], [by0,by0,by1,by1,by0],
                color='#b0b0b0', lw=1.0, linestyle='--', alpha=0.7, zorder=0.5,
                label='Plot (before recenter)')

    # Site fill + boundary (after recenter)
    ax.fill([px0,px1,px1,px0,px0], [py0,py0,py1,py1,py0], color='#f0f8ff', zorder=0)
    ax.plot([px0,px1,px1,px0,px0], [py0,py0,py1,py1,py0], color='black', lw=1.2, zorder=1)

    # 2m grid
    if show_grid:
        cs = CELL_SIZE
        for i in range(int(sw // cs) + 1):
            ax.axvline(i * cs, color='#dddddd', lw=0.2, zorder=0.1)
        for j in range(int(sl // cs) + 1):
            ax.axhline(j * cs, color='#dddddd', lw=0.2, zorder=0.1)


    if show_a1_ring:  # → §3.4.A (ring road) · §3.4.B (gate spur) · §3.4.D (ring spur)
        # Ring road (loop)
        if ring_road:
            draw_road_with_fillets(ax, ring_road, width=8, color='#7f8c8d', fillet_radius=14.0, alpha=0.95, zorder=1.5,
                                   label='§3.4.A Ring Road', is_closed=True)

        # Gate & Ring spurs
        gs = sketch.get("gate_spur") or []
        rs = sketch.get("ring_spur") or []
        if gs and rs:
            combined_spur = list(rs) + list(gs)[1:]
            draw_road_with_fillets(ax, combined_spur, width=8, color='#7f8c8d', fillet_radius=14.0, alpha=0.95, zorder=1.5,
                                   label='§3.4.B/D Gate & Ring Spur', is_closed=False)
        else:
            if gs:
                draw_road_with_fillets(ax, gs, width=8, color='#7f8c8d', fillet_radius=14.0, alpha=0.95, zorder=1.5, is_closed=False)
            if rs:
                draw_road_with_fillets(ax, rs, width=8, color='#7f8c8d', fillet_radius=14.0, alpha=0.95, zorder=1.5, is_closed=False)


    # Default buffer halos per block — magnetic snap boundaries  [→ §3.5.B gap rules]
    #  - Rack blocks: 14m road buffer (so two rack blocks touching sit 28m apart)
    #  - No-rack blocks: 8m road buffer (so two no-rack touching sit 16m apart)
    if show_buffer:
        legended_buffers = set()
        for b in blocks:
            is_rack = b["name"] in Core.Stage01.RACK_BLOCKS
            snap_buf = Core.Stage01.ROAD_W_RACK_OFFSET if is_rack else Core.Stage01.ROAD_BUFFER
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
            ("case1_rack",   '§3.6.A Case 1 CL (8m)',      '#00b894', '-',  1.6, show_rack_w_rack),
            ("road_w_rack",  '§3.6.A 16m road (w-rack)',   '#2980b9', '-',  1.2, show_rack_w_rack),
            ("case2_rack",   '§3.6.A Case 2 CL (24m)',     '#8e44ad', ':',  1.4, show_rack_w_rack),
            ("b2b_w_rack",   '§3.6.A 30m b2b (w-rack)',    '#e67e22', ':',  1.0, show_rack_w_rack),
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
        with open("debug_draw.txt", "w", encoding="utf-8") as f:
            for seg in rack_segments:
                f.write(f"plotting: {seg}\n")
        draw_network_squared(ax, rack_segments, width=6, color='#d35400', zorder=3.5,
                             label='§3.6.B Rack Spines')
        

    if show_spine_debug:
        spine_centerlines = sketch.get("spine_centerlines") or []
        water_cluster_segments = sketch.get("water_cluster_segments") or []
        pruned_rack_segments = sketch.get("pruned_rack_segments", [])
        
        # Plot raw spine centerlines as thick dashed green lines
        for i, seg in enumerate(spine_centerlines):
            p1, p2 = seg
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='#2ecc71', linestyle='--', linewidth=2.5, alpha=0.9, zorder=3.8,
                    label='Raw Spine Centerlines (PB-CT)' if i == 0 else "")
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 'o', color='#27ae60', markersize=6, zorder=3.9)
            
        # Plot water cluster segments as thick dashed cyan lines
        for i, seg in enumerate(water_cluster_segments):
            p1, p2 = seg
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='#00d2d3', linestyle='--', linewidth=2.5, alpha=0.9, zorder=3.8,
                    label='Water Cluster Spine (Raw)' if i == 0 else "")
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 'o', color='#01a3a4', markersize=6, zorder=3.9)

        # Plot pruned segments
        if pruned_rack_segments:
            draw_network_squared(ax, pruned_rack_segments, width=6, color='#bdc3c7', alpha=0.4, zorder=3.4,
                                 label='Pruned Rack Segments')
                
        # Candidate points (B-2, B-3)  [→ §3.6.B]
        # (Disabled by user request)
        # rack_candidates = sketch.get("rack_candidates", [])
        # for i, pt in enumerate(rack_candidates):
        #     ax.plot(pt[0], pt[1], 'o', color='#bdc3c7', markersize=4, zorder=3.6, 
        #             label='§3.6.B B-2/B-3 Candidates' if i==0 else "")

        # Water Triangle (B-4)  [→ §3.6.B]
        # (Disabled by user request)
        # water_triangle = sketch.get("water_triangle", [])
        # for i, pt in enumerate(water_triangle):
        #     ax.plot(pt[0], pt[1], '*', color='#f1c40f', markersize=12, markeredgecolor='black', zorder=3.7, 
        #             label='§3.6.B B-4 Triangle' if i==0 else "")
        # if len(water_triangle) == 3:
        #     # Draw lines connecting them
        #     wx, wy = zip(*(water_triangle + [water_triangle[0]]))
        #     ax.plot(wx, wy, color='#f1c40f', linestyle=':', linewidth=1, zorder=3.6)

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

    # Gate marker — recentered (solid) + before recenter (faded, if different)
    gb = sketch.get("gate_point_before")
    if show_before_recenter and gb and (abs(gb[0] - gate_pt[0]) > 0.1 or abs(gb[1] - gate_pt[1]) > 0.1):
        ax.plot(gb[0], gb[1], '^', color='#27ae60', markersize=14, alpha=0.35,
                zorder=5.5, markeredgecolor='white', markeredgewidth=1.0,
                label='Gate (before recenter)')
        ax.text(gb[0], gb[1] + 8, 'gate (before)', color='#27ae60', fontsize=7,
                alpha=0.6, ha='center', va='bottom', zorder=5.5)
    gx, gy = gate_pt
    ax.plot(gx, gy, '^', color='#27ae60', markersize=14, zorder=6,
            markeredgecolor='white', markeredgewidth=1.0)
    ax.text(gx, gy + 8, 'GATE', color='#27ae60', fontsize=9,
            fontweight='bold', ha='center', va='bottom', zorder=6)

    ax.set_xlim(min(0, px0) - 20, max(sw, px1) + 20)
    ax.set_ylim(min(0, py0) - 20, max(sl, py1) + 20)
    ax.set_aspect('equal', adjustable='box')
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_visible(False)
    if show_legend:
        ax.legend(loc='upper left', fontsize=8, framealpha=0.9)

    plt.tight_layout(pad=0.4)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

    # Placement pass banner — shown below the layout
    _dbg = Core.Stage01._last_debug
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
        gc = Core.Stage01._last_debug.get("pb_gate_check")
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

    with st.expander("§3.6.B Debug — PB-CT Spine Creation"):
        sc = Core.Stage01._last_debug.get("spine_creation")
        if sc:
            st.write(f"**Power Block Case:** `{sc.get('pb_case')}`")
            st.write(f"**Cooling Tower Case:** `{sc.get('ct_case')}`")
            st.write(f"**Horizontal Overlap?** `{sc.get('is_horizontal')}` | **Vertical Overlap?** `{sc.get('is_vertical')}`")
            st.write(f"**Overlap Detected?** `{sc.get('overlap')}` | **Overlap reroute (A* around block)?** `{sc.get('overlap_reroute', False)}`")
            hits = sketch.get("pb_buffer_hits") or sc.get("pb_buffer_hits") or []
            hits_str = ", ".join(f"({round(p[0], 1)}, {round(p[1], 1)})" for p in hits)
            st.write(f"**Spine × PB case1 buffer (cut):** `{hits_str or 'none'}`")
            mro = sketch.get("main_rack_output") or sc.get("main_rack_output")
            if mro:
                st.write(f"**MAIN RACK output:** `({round(mro[0][0],1)}, {round(mro[0][1],1)}) → "
                         f"({round(mro[1][0],1)}, {round(mro[1][1],1)})`")
        else:
            st.warning("no spine_creation in debug metadata")

        # Table of all rack spans
        import pandas as pd
        import math

        segments_data = []

        # 1. Spine centerlines
        spine_centerlines = sketch.get("spine_centerlines") or []
        for i, s in enumerate(spine_centerlines):
            x1, y1 = s[0]
            x2, y2 = s[1]
            L = math.hypot(x2 - x1, y2 - y1)
            direction = "Horizontal" if abs(y2 - y1) < 0.1 else ("Vertical" if abs(x2 - x1) < 0.1 else "Skewed")
            segments_data.append({
                "Span Type": f"Spine Centerline [{i+1}]",
                "Start Point": f"({round(x1, 1)}, {round(y1, 1)})",
                "End Point": f"({round(x2, 1)}, {round(y2, 1)})",
                "Length (m)": round(L, 2),
                "Direction": direction
            })

        # 2. Water cluster segments
        water_cluster_segments = sketch.get("water_cluster_segments") or []
        for i, s in enumerate(water_cluster_segments):
            x1, y1 = s[0]
            x2, y2 = s[1]
            L = math.hypot(x2 - x1, y2 - y1)
            direction = "Horizontal" if abs(y2 - y1) < 0.1 else ("Vertical" if abs(x2 - x1) < 0.1 else "Skewed")
            segments_data.append({
                "Span Type": f"Water Cluster Spine [{i+1}]",
                "Start Point": f"({round(x1, 1)}, {round(y1, 1)})",
                "End Point": f"({round(x2, 1)}, {round(y2, 1)})",
                "Length (m)": round(L, 2),
                "Direction": direction
            })

        # 3. Final rack segments (spines + connections)
        rack_segments = sketch.get("rack_segments") or []
        for i, s in enumerate(rack_segments):
            x1, y1 = s[0]
            x2, y2 = s[1]
            L = math.hypot(x2 - x1, y2 - y1)
            direction = "Horizontal" if abs(y2 - y1) < 0.1 else ("Vertical" if abs(x2 - x1) < 0.1 else "Skewed")
            segments_data.append({
                "Span Type": f"Final Connected Span [{i+1}]",
                "Start Point": f"({round(x1, 1)}, {round(y1, 1)})",
                "End Point": f"({round(x2, 1)}, {round(y2, 1)})",
                "Length (m)": round(L, 2),
                "Direction": direction
            })

        # 4. Pruned segments
        pruned_rack_segments = sketch.get("pruned_rack_segments") or []
        for i, s in enumerate(pruned_rack_segments):
            x1, y1 = s[0]
            x2, y2 = s[1]
            L = math.hypot(x2 - x1, y2 - y1)
            direction = "Horizontal" if abs(y2 - y1) < 0.1 else ("Vertical" if abs(x2 - x1) < 0.1 else "Skewed")
            segments_data.append({
                "Span Type": f"Pruned Segment [{i+1}]",
                "Start Point": f"({round(x1, 1)}, {round(y1, 1)})",
                "End Point": f"({round(x2, 1)}, {round(y2, 1)})",
                "Length (m)": round(L, 2),
                "Direction": direction
            })

        if segments_data:
            st.markdown("#### All Rack Spans / Segments")
            df_segs = pd.DataFrame(segments_data)
            st.dataframe(df_segs, use_container_width=True, hide_index=True)
            
            # Add a copy-pasteable data block
            st.markdown("#### 📋 Copy-Paste Coordinates")
            st.code(
                f"spine_centerlines = {spine_centerlines}\n\n"
                f"main_rack_output = {sketch.get('main_rack_output')}\n\n"
                f"pb_buffer_hits = {sketch.get('pb_buffer_hits') or []}\n\n"
                f"water_cluster_segments = {water_cluster_segments}\n\n"
                f"pruned_rack_segments = {pruned_rack_segments}\n\n"
                f"final_rack_segments = {rack_segments}",
                language="python"
            )



    # Stats
    st.divider()
    st.markdown("#### Block stats")
    rows = [{"Block": b["name"], "X (m)": b["x"], "Y (m)": b["y"],
             "W (m)": b["width"], "H (m)": b["height"]} for b in blocks]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    # Position before / after recenter (§3.8). The plot moves by recenter_delta,
    # so a block/road keeps its world coords but sits at (world − delta)
    # relative to the recentered plot — useful to check it still fits [0,sw]×[0,sl].
    dx, dy = sketch.get("recenter_delta", (0, 0))
    st.markdown("#### Block + Road/Spur position (before / after recenter)")
    st.caption(f"recenter_delta = ({dx:.1f}, {dy:.1f}). 'After' = position relative to the recentered plot (world − delta).")
    pos_rows = []
    for b in blocks:
        pos_rows.append({"Element": b["name"],
                         "X before": round(b["x"], 1), "Y before": round(b["y"], 1),
                         "X after": round(b["x"] - dx, 1), "Y after": round(b["y"] - dy, 1)})
    for label, key in (("Ring Road", "ring_road"), ("Gate Spur", "gate_spur"), ("Ring Spur", "ring_spur")):
        poly = sketch.get(key)
        if poly:
            ax, ay = poly[0][0], poly[0][1]
            pos_rows.append({"Element": f"{label} (start)",
                             "X before": round(ax, 1), "Y before": round(ay, 1),
                             "X after": round(ax - dx, 1), "Y after": round(ay - dy, 1)})
    st.dataframe(pos_rows, use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    c1.metric("Blocks placed", len(blocks))
    c2.metric("Grid cell size", f"{CELL_SIZE}m")
