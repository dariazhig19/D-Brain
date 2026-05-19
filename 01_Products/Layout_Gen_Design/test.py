import sys
sys.path.append('Core')
import Main

def run_diagnostics():
    sw, sl = 500, 270
    wind_dir = 'East'
    gate_side, gate_ratio = 'N', 0.6
    gh_edge, gh_ratio, gh_offset = 'N', 0.5, 0
    gis_edge, gis_ratio, gis_offset = 'N', 1.0, 5
    water_edge, water_ratio, water_offset = 'S', 0.05, 20
    boundary_margin = -50
    
    gate_point = Main.compute_gate_point(gate_side, gate_ratio, sw, sl)
    
    reasons = {
        'Power Block': 0,
        'Cooling Tower': 0,
        'WT/WWT': 0,
        'Warehouse': 0,
        'Flare': 0,
        'Admin Building': 0,
        'Demi Water Tank': 0,
        'Overlap Sanity': 0,
        'Road Network': 0,
        'Rack Overlap': 0
    }
    
    for _ in range(300):
        placed = {}
        gh_x, gh_y, gh_rot = Main._place_anchor(sw, sl, "Gate House", gh_edge, gh_ratio, gh_offset)
        placed["Gate House"] = (gh_x, gh_y, gh_rot)
        gis_x, gis_y, gis_rot = Main._place_anchor(sw, sl, "GIS", gis_edge, gis_ratio, gis_offset)
        placed["GIS"] = (gis_x, gis_y, gis_rot)
        water_x, water_y, water_rot = Main._place_anchor(sw, sl, "RAW Water Tank", water_edge, water_ratio, water_offset)
        placed["RAW Water Tank"] = (water_x, water_y, water_rot)
        
        result = Main._try_place_collision_aware(sw, sl, "Power Block", placed,
                    lambda: Main._place_power_block(sw, sl, boundary_margin), max_attempts=50)
        if result is None: reasons['Power Block'] += 1; continue
        placed["Power Block"] = result
        pb_center = (result[0] + Main._FP["Power Block"][0]/2, result[1] + Main._FP["Power Block"][1]/2)

        result = Main._try_place_collision_aware(sw, sl, "Cooling Tower", placed,
                    lambda: Main._place_cooling_tower(sw, sl, wind_dir, boundary_margin), max_attempts=500, pb_center=pb_center)
        if result is None: reasons['Cooling Tower'] += 1; continue
        placed["Cooling Tower"] = result

        result = Main._try_place_collision_aware(sw, sl, "WT/WWT", placed,
                    lambda: Main._place_wt_wwt(sw, sl, water_x, water_y, water_rot, boundary_margin), max_attempts=500, pb_center=pb_center)
        if result is None: reasons['WT/WWT'] += 1; continue
        placed["WT/WWT"] = result

        result = Main._try_place_collision_aware(sw, sl, "Warehouse", placed,
                    lambda: Main._place_warehouse(sw, sl, boundary_margin), max_attempts=500, pb_center=pb_center)
        if result is None: reasons['Warehouse'] += 1; continue
        placed["Warehouse"] = result

        result = Main._try_place_collision_aware(sw, sl, "Flare", placed,
                    lambda: Main._place_flare(sw, sl, wind_dir, boundary_margin), max_attempts=500, pb_center=pb_center)
        if result is None: reasons['Flare'] += 1; continue
        placed["Flare"] = result

        result = Main._try_place_collision_aware(sw, sl, "Admin Building", placed,
                    lambda: Main._place_admin(sw, sl, boundary_margin), max_attempts=500, pb_center=pb_center, gate_point=gate_point)
        if result is None: reasons['Admin Building'] += 1; continue
        placed["Admin Building"] = result

        result = Main._try_place_collision_aware(sw, sl, "Demi Water Tank", placed,
                    lambda: Main._place_demi_water(sw, sl, water_x, water_y, water_rot, boundary_margin), max_attempts=500, pb_center=None)
        if result is None: reasons['Demi Water Tank'] += 1; continue
        placed["Demi Water Tank"] = result

        positions = dict(placed)
        if Main._has_any_overlap(positions): reasons['Overlap Sanity'] += 1; continue
        
        groups = Main.get_all_groups(sw, sl, positions=positions)
        road = Main.build_road_network(sw, sl, groups, gate_point)
        if road is None: reasons['Road Network'] += 1; continue
        
        rack_segments = Main._place_racks(groups)
        racks = Main.get_all_racks(groups, rack_segments=rack_segments)
        
        overlap_found = False
        for rack in racks:
            for p1, p2 in rack["segments"]:
                for g in groups:
                    if Main._line_intersects_rect(p1, p2, g["x"]+1, g["y"]+1, g["width"]-2, g["height"]-2):
                        overlap_found = True
                        break
                if overlap_found: break
            if overlap_found: break
            
        if overlap_found: reasons['Rack Overlap'] += 1; continue

    print("Rejection reasons for 300 iterations:")
    for k, v in reasons.items():
        if v > 0:
            print(f" - {k}: {v}")

if __name__ == '__main__':
    run_diagnostics()
