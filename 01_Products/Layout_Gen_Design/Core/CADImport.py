"""CADImport — read a plot definition from a DXF drawing (Phase 06 polygon migration).

The user draws the site in CAD and exports **DXF** (DWG is a proprietary binary
format Python cannot read directly — export DXF, or convert with the free ODA
File Converter first). Each element lives on a named layer:

    Layer                      Geometry             → meaning
    ─────────────────────────  ───────────────────  ──────────────────────────
    Plot                       LWPOLYLINE/POLYLINE  convex polygon (≤6 verts)
    Gate                       CIRCLE               center = gate point on boundary
    Gate House                 rectangle polyline   fixed anchor footprint
    RAW Tank                   rectangle polyline   fixed anchor footprint
    GIS                        rectangle polyline   fixed anchor footprint
    Gate House Boom Barrier    LINE                 boom barrier; midpoint = bb_mid

Returns a plain dict (engine stays UI-free). Geometry is returned in DXF/world
coordinates; the engine/dashboard decide whether to normalise the origin.

Result shape:
    {
        "plot_polygon": [(x, y), ...],          # ordered vertices (raw, from DXF)
        "gate_point":   (x, y) | None,
        "boom_barrier": [(x1, y1), (x2, y2)] | None,
        "anchors": {                            # name → (x, y, w, h) AABB footprint
            "Gate House": (...), "RAW Water Tank": (...), "GIS": (...),
        },
        "warnings": [str, ...],                 # non-fatal layer/geometry issues
    }
"""

import ezdxf

__all__ = ["load_plot_dxf", "LAYER_ALIASES"]

# Map drawing layer names → canonical engine names. Case-insensitive, trimmed.
LAYER_ALIASES = {
    "plot": "Plot",
    "gate": "Gate",
    "gate house": "Gate House",
    "gatehouse": "Gate House",
    "raw tank": "RAW Water Tank",
    "raw water tank": "RAW Water Tank",
    "raw water": "RAW Water Tank",
    "gis": "GIS",
    "gate house boom barrier": "Boom Barrier",
    "boom barrier": "Boom Barrier",
    "boom": "Boom Barrier",
}


def _canon(layer_name):
    return LAYER_ALIASES.get(layer_name.strip().lower())


def _polyline_points(entity):
    """Return [(x, y), ...] for an LWPOLYLINE or 2D/3D POLYLINE."""
    dxftype = entity.dxftype()
    if dxftype == "LWPOLYLINE":
        return [(p[0], p[1]) for p in entity.get_points("xy")]
    if dxftype == "POLYLINE":
        return [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
    if dxftype == "LINE":
        return [(entity.dxf.start.x, entity.dxf.start.y),
                (entity.dxf.end.x, entity.dxf.end.y)]
    return []


def _aabb(points):
    """Axis-aligned bounding box of points → (x, y, w, h)."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, y0 = min(xs), min(ys)
    return (x0, y0, max(xs) - x0, max(ys) - y0)


def _read_document(path):
    """Open a DXF directly, or a DWG via the ODA File Converter add-on.

    DWG is a proprietary binary format ezdxf cannot parse. If the user supplies a
    .dwg we route through ``ezdxf.addons.odafc``, which shells out to the free
    ODA File Converter (must be installed separately). A clear error is raised if
    it is missing, telling the user to export DXF instead.
    """
    lower = path.lower()
    if lower.endswith(".dwg"):
        try:
            from ezdxf.addons import odafc
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(
                "DWG import needs the ODA File Converter add-on (ezdxf.addons.odafc). "
                "Install the free ODA File Converter, or export the drawing as DXF."
            ) from ex
        try:
            return odafc.readfile(path)
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(
                "Could not convert DWG — the ODA File Converter executable was not "
                "found. Install it from https://www.opendesign.com/guestfiles/oda_file_converter, "
                "or in AutoCAD use 'Save As → AutoCAD DXF (*.dxf)' and upload the DXF."
            ) from ex
    return ezdxf.readfile(path)


def _circle_aabb(entity):
    """AABB (x, y, w, h) of a CIRCLE — center ± radius."""
    c = entity.dxf.center
    r = entity.dxf.radius
    return (c.x - r, c.y - r, 2 * r, 2 * r)


def _entity_footprint(entity):
    """AABB footprint of any supported anchor entity, or None."""
    if entity.dxftype() == "CIRCLE":
        return _circle_aabb(entity)
    pts = _polyline_points(entity)
    return _aabb(pts) if len(pts) >= 2 else None


def load_plot_dxf(path, scale=None, to_origin=True):
    """Parse a plot DXF/DWG into the engine input dict.

    Parameters
    ----------
    scale : float | None
        Multiply every coordinate by this. The engine works in **metres** and
        block footprints are in metres, so a drawing in millimetres needs
        ``scale=0.001``. ``None`` (default) **auto-detects** mm vs m by comparing
        the drawn GIS footprint to its catalogue size (110×51 m); falls back to
        1.0 if GIS is absent. Detection is reported in ``warnings``.
    to_origin : bool
        If True, translate all geometry so the plot's bounding-box minimum sits
        at (0, 0) — matching the engine's origin-based heuristics.

    Raises on an unreadable file.
    """
    doc = _read_document(path)
    msp = doc.modelspace()

    result = {
        "plot_polygon": None,
        "gate_point": None,
        "boom_barrier": None,
        "anchors": {},
        "warnings": [],
    }
    rect_anchor_layers = {"Gate House", "RAW Water Tank", "GIS"}
    layer0_geometry = 0

    for e in msp:
        # Flag drawn geometry stranded on the default layer '0' (a common
        # "forgot to set the layer" mistake — e.g. Gate House left on layer 0).
        if e.dxf.layer == "0" and e.dxftype() in ("LWPOLYLINE", "POLYLINE", "CIRCLE", "LINE"):
            layer0_geometry += 1

        canon = _canon(e.dxf.layer)
        if canon is None:
            continue
        dxftype = e.dxftype()

        if canon == "Plot":
            pts = _polyline_points(e)
            if len(pts) >= 3:
                if len(pts) > 3 and abs(pts[0][0] - pts[-1][0]) < 1e-6 and abs(pts[0][1] - pts[-1][1]) < 1e-6:
                    pts = pts[:-1]
                result["plot_polygon"] = pts
            else:
                result["warnings"].append(f"Plot layer entity {dxftype} has <3 points; ignored")

        elif canon == "Gate":
            if dxftype == "CIRCLE":
                c = e.dxf.center
                result["gate_point"] = (c.x, c.y)
            elif dxftype == "POINT":
                p = e.dxf.location
                result["gate_point"] = (p.x, p.y)
            else:
                fp = _entity_footprint(e)
                if fp:
                    result["gate_point"] = (fp[0] + fp[2] / 2, fp[1] + fp[3] / 2)
                    result["warnings"].append(f"Gate drawn as {dxftype}; used its center")

        elif canon == "Boom Barrier":
            pts = _polyline_points(e)
            if len(pts) >= 2:
                result["boom_barrier"] = [pts[0], pts[-1]]
            else:
                result["warnings"].append(f"Boom Barrier {dxftype} has <2 points; ignored")

        elif canon in rect_anchor_layers:
            fp = _entity_footprint(e)
            if fp:
                result["anchors"][canon] = fp
            else:
                result["warnings"].append(f"{canon} {dxftype} could not be read; ignored")

    # ── Unit scaling (mm/m auto-detect) ──────────────────────────────────
    if scale is None:
        scale = _detect_scale(result, result["warnings"])
    if scale != 1.0:
        _apply_scale(result, scale)
        result["warnings"].append(f"Applied unit scale ×{scale} (→ metres).")
    result["scale"] = scale

    # ── Origin normalisation ─────────────────────────────────────────────
    if to_origin and result["plot_polygon"]:
        xs = [p[0] for p in result["plot_polygon"]]
        ys = [p[1] for p in result["plot_polygon"]]
        ox, oy = min(xs), min(ys)
        if abs(ox) > 1e-6 or abs(oy) > 1e-6:
            _apply_shift(result, -ox, -oy)
            result["warnings"].append(f"Shifted to origin (was offset by {ox:.1f}, {oy:.1f}).")
    result["origin_shift"] = None  # set by _apply_shift if used

    # Cast every coordinate to plain float (ezdxf hands back numpy floats).
    _finalize_floats(result)

    # ── Sanity warnings (non-fatal) ──────────────────────────────────────
    if result["plot_polygon"] is None:
        result["warnings"].append("No 'Plot' polygon found.")
    if result["gate_point"] is None:
        result["warnings"].append("No 'Gate' circle found.")
    for required in rect_anchor_layers:
        if required not in result["anchors"]:
            result["warnings"].append(f"No '{required}' anchor found.")
    if layer0_geometry:
        result["warnings"].append(
            f"{layer0_geometry} object(s) on layer '0' were ignored — assign them "
            f"to a named layer (e.g. an empty 'Gate House' layer suggests it was "
            f"drawn on layer 0).")

    return result


# ── Normalisation helpers ────────────────────────────────────────────────
def _detect_scale(result, warnings):
    """Detect mm→m by comparing the drawn GIS footprint to its 110×51 m catalogue size."""
    gis = result["anchors"].get("GIS")
    if not gis:
        return 1.0
    drawn_w = max(gis[2], gis[3])  # long side, orientation-agnostic
    catalogue_long = 110.0
    if drawn_w <= 0:
        return 1.0
    ratio = drawn_w / catalogue_long
    # Snap to the nearest common unit factor.
    for factor, name in [(1.0, "m"), (0.001, "mm"), (0.01, "cm"), (0.0254, "in")]:
        if abs(drawn_w * factor - catalogue_long) / catalogue_long < 0.25:
            if factor != 1.0:
                warnings.append(f"Auto-detected drawing units: {name} (GIS long side {drawn_w:.0f}).")
            return factor
    warnings.append(f"Could not match GIS size {drawn_w:.0f} to a unit; assuming metres.")
    return 1.0


def _finalize_floats(result):
    if result["plot_polygon"]:
        result["plot_polygon"] = [(float(x), float(y)) for x, y in result["plot_polygon"]]
    if result["gate_point"]:
        result["gate_point"] = (float(result["gate_point"][0]), float(result["gate_point"][1]))
    if result["boom_barrier"]:
        result["boom_barrier"] = [(float(x), float(y)) for x, y in result["boom_barrier"]]
    result["anchors"] = {k: tuple(float(v) for v in rect) for k, rect in result["anchors"].items()}


def _scale_pt(p, s):
    return (p[0] * s, p[1] * s)


def _apply_scale(result, s):
    if result["plot_polygon"]:
        result["plot_polygon"] = [_scale_pt(p, s) for p in result["plot_polygon"]]
    if result["gate_point"]:
        result["gate_point"] = _scale_pt(result["gate_point"], s)
    if result["boom_barrier"]:
        result["boom_barrier"] = [_scale_pt(p, s) for p in result["boom_barrier"]]
    result["anchors"] = {k: tuple(v * s for v in rect) for k, rect in result["anchors"].items()}


def _apply_shift(result, dx, dy):
    if result["plot_polygon"]:
        result["plot_polygon"] = [(p[0] + dx, p[1] + dy) for p in result["plot_polygon"]]
    if result["gate_point"]:
        gp = result["gate_point"]
        result["gate_point"] = (gp[0] + dx, gp[1] + dy)
    if result["boom_barrier"]:
        result["boom_barrier"] = [(p[0] + dx, p[1] + dy) for p in result["boom_barrier"]]
    result["anchors"] = {k: (rect[0] + dx, rect[1] + dy, rect[2], rect[3])
                         for k, rect in result["anchors"].items()}


def summarize(result):
    """Short human-readable summary of a load_plot_dxf result (dashboard aid)."""
    lines = []
    poly = result.get("plot_polygon")
    lines.append(f"Plot: {len(poly)} vertices" if poly else "Plot: MISSING")
    lines.append(f"Gate: {result['gate_point']}" if result.get("gate_point") else "Gate: MISSING")
    lines.append(f"Boom: {'yes' if result.get('boom_barrier') else 'no'}")
    for name, rect in result.get("anchors", {}).items():
        x, y, w, h = rect
        lines.append(f"{name}: ({x:.0f},{y:.0f}) {w:.0f}×{h:.0f}")
    return "\n".join(lines)
