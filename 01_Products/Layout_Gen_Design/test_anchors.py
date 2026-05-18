import sys
sys.path.insert(0, ".")

from Core.Main import generate_layouts

print("Testing the new Anchor Placements...")
res = generate_layouts(
    site_width=500, site_length=270, wind_dir="East",
    n_results=1, min_rules_passing=1, max_pool=100,
    gate_side="N", gate_ratio=0.5,
    gh_edge="N", gh_ratio=0.5, gh_offset=0,
    gis_edge="N", gis_ratio=0.8, gis_offset=0,
    water_edge="N", water_ratio=0.2, water_offset=0,
    boundary_margin=-20
)

print(f"Generated: {len(res)} layouts")
if len(res) > 0:
    print("SUCCESS: Anchor placements and generation are working!")
else:
    print("FAILURE: Still unable to generate.")
