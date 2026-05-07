"""
Core/RuleNetwork.py
Generates an interactive Pyvis rule network graph from the RULES data list.
Run directly: python Core/RuleNetwork.py
Output: Notes/Rule_Network.html
"""

import os
import sys
import networkx as nx
from pyvis.network import Network

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Core.Rules import RULES
from Core.Groups import GROUP_COLORS, RACK_COLORS, FOOTPRINTS, RACK_WIDTHS


# ── Node sizing ────────────────────────────────────────────────────────────

def _node_size(name):
    """Scale node size by footprint area (or fixed for racks/virtual nodes)."""
    if name in FOOTPRINTS:
        w, h = FOOTPRINTS[name]
        return max(15, min(50, int((w * h) ** 0.35)))
    if name in RACK_WIDTHS:
        return 12
    return 10  # virtual nodes (Plot Center, Wind Direction, Primary Road)


def _node_color(name):
    """Get color for a node."""
    if name in GROUP_COLORS:
        return GROUP_COLORS[name]
    if name in RACK_COLORS:
        return RACK_COLORS[name]
    # Virtual nodes
    return "#cccccc"


def _node_shape(name):
    """Get shape: buildings = box, racks = diamond, virtual = dot."""
    if name in FOOTPRINTS:
        return "box"
    if name in RACK_WIDTHS:
        return "diamond"
    return "dot"


# ── Edge styling by rule type ──────────────────────────────────────────────

RULE_TYPE_STYLES = {
    "center_proximity":    {"color": "#3498db", "dashes": False, "width": 2},
    "boundary_setback":    {"color": "#e74c3c", "dashes": [5, 5], "width": 1.5},
    "windward_edge":       {"color": "#2ecc71", "dashes": [10, 5], "width": 2},
    "min_distance":        {"color": "#e67e22", "dashes": False, "width": 2.5},
    "max_distance":        {"color": "#9b59b6", "dashes": False, "width": 2.5},
    "pipe_rack_proximity": {"color": "#95a5a6", "dashes": [3, 3], "width": 2},
}


# ── Build graph ────────────────────────────────────────────────────────────

def build_rule_graph():
    """Build a NetworkX graph from the RULES data list."""
    G = nx.Graph()

    # Collect all unique node names
    all_nodes = set()
    for rule in RULES:
        all_nodes.add(rule["group"])
        all_nodes.add(rule["target"])

    # Add nodes
    for name in all_nodes:
        G.add_node(name,
                   size=_node_size(name),
                   color=_node_color(name),
                   shape=_node_shape(name),
                   title=name)

    # Add edges
    for rule in RULES:
        style = RULE_TYPE_STYLES.get(rule["type"], {"color": "#aaa", "dashes": False, "width": 1})
        label = f"{rule['id']}: {rule['type']}\n({rule['threshold']}m, {rule['penalty_rate']}pts)"
        title = (
            f"<b>{rule['id']}</b><br>"
            f"Type: {rule['type']}<br>"
            f"Group: {rule['group']}<br>"
            f"Target: {rule['target']}<br>"
            f"Threshold: {rule['threshold']} m<br>"
            f"Penalty: {rule['penalty_rate']} pts/{rule['penalty_mode']}"
        )
        G.add_edge(
            rule["group"], rule["target"],
            label=rule["id"],
            title=title,
            color=style["color"],
            width=style["width"],
            dashes=style["dashes"],
        )

    return G


def export_pyvis_html(G, output_path):
    """Render the graph as an interactive Pyvis HTML file."""
    net = Network(
        height="700px",
        width="100%",
        bgcolor="#1a1a2e",
        font_color="#ffffff",
        directed=False,
        notebook=False,
    )

    # Physics settings
    net.barnes_hut(
        gravity=-3000,
        central_gravity=0.3,
        spring_length=200,
        spring_strength=0.05,
        damping=0.09,
    )

    # Transfer nodes
    for node, data in G.nodes(data=True):
        net.add_node(
            node,
            label=node,
            size=data.get("size", 20),
            color=data.get("color", "#cccccc"),
            shape=data.get("shape", "dot"),
            title=data.get("title", node),
            font={"size": 14, "color": "#ffffff", "face": "Arial"},
            borderWidth=2,
            borderWidthSelected=4,
        )

    # Transfer edges
    for u, v, data in G.edges(data=True):
        net.add_edge(
            u, v,
            label=data.get("label", ""),
            title=data.get("title", ""),
            color=data.get("color", "#aaaaaa"),
            width=data.get("width", 1),
            dashes=data.get("dashes", False),
            font={"size": 10, "color": "#aaaaaa", "face": "Arial", "align": "middle"},
        )

    # Enable physics toggle button
    net.toggle_physics(True)

    net.save_graph(output_path)
    print(f"[OK] Rule Network saved to: {output_path}")


# ── Legend HTML injection ──────────────────────────────────────────────────

def _inject_legend(output_path):
    """Inject a floating legend into the HTML file."""
    legend_html = """
    <div style="position:fixed; top:10px; right:10px; background:rgba(26,26,46,0.95);
                border:1px solid #444; border-radius:8px; padding:15px; z-index:1000;
                font-family:Arial; color:#fff; font-size:12px; max-width:220px;">
        <div style="font-size:14px; font-weight:bold; margin-bottom:10px; color:#f0f0f0;">
            🔗 Rule Types
        </div>
        <div style="margin-bottom:5px;"><span style="color:#3498db;">━━</span> center_proximity</div>
        <div style="margin-bottom:5px;"><span style="color:#e74c3c;">╌╌</span> boundary_setback</div>
        <div style="margin-bottom:5px;"><span style="color:#2ecc71;">━ ╌</span> windward_edge</div>
        <div style="margin-bottom:5px;"><span style="color:#e67e22;">━━</span> min_distance</div>
        <div style="margin-bottom:5px;"><span style="color:#9b59b6;">━━</span> max_distance</div>
        <div style="margin-bottom:5px;"><span style="color:#95a5a6;">╌╌</span> pipe_rack_proximity</div>
        <hr style="border-color:#444; margin:10px 0;">
        <div style="font-size:11px; color:#888;">
            ◼ Box = Building &nbsp; ◆ Diamond = Rack &nbsp; ● Dot = Reference
        </div>
    </div>
    """
    with open(output_path, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("</body>", legend_html + "\n</body>")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


# ── CLI entry point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    output = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Notes', 'Rule_Network.html'))
    G = build_rule_graph()
    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    export_pyvis_html(G, output)
    _inject_legend(output)
    print(f"Open in browser: file:///{output.replace(os.sep, '/')}")
