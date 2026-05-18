import sys
sys.path.insert(0, ".")

from Core.Main import (
    _place_anchor, _try_place_collision_aware, _place_power_block,
    _place_admin, _place_cooling_tower, _place_wt_wwt, _place_flare,
    _place_lpg, _place_warehouse, _has_any_overlap, _OVERLAP_GAP, _place_demi_water
)

sw, sl = 500, 270
margin = -20
print(f"Testing with _OVERLAP_GAP = {_OVERLAP_GAP}")

for i in range(10):
    placed = {}
    
    # Anchors
    placed["Gate House"] = _place_anchor(sw, sl, "Gate House", "N", 0.5, 0)
    placed["GIS"] = _place_anchor(sw, sl, "GIS", "N", 0.8, 0)
    water = _place_anchor(sw, sl, "RAW Water Tank", "N", 0.2, 0)
    placed["RAW Water Tank"] = water
    
    demi = _place_demi_water(sw, sl, water[0], water[1], water[2], placed, margin)
    if demi is None:
        print(f"Failed to place Demi Water Tank on iteration {i}")
        continue
    placed["Demi Water Tank"] = demi
    
    pb = _try_place_collision_aware(sw, sl, "Power Block", placed, lambda: _place_power_block(sw, sl, margin))
    if pb is None:
        print(f"Failed to place Power Block on iteration {i}")
        continue
    placed["Power Block"] = pb
    
    adm = _try_place_collision_aware(sw, sl, "Admin Building", placed, lambda: _place_admin(sw, sl, placed["Gate House"][0], placed["Gate House"][1], pb[0], pb[1], margin))
    if adm is None:
        print(f"Failed to place Admin on iteration {i}")
        continue
    placed["Admin Building"] = adm
    
    ct = _try_place_collision_aware(sw, sl, "Cooling Tower", placed, lambda: _place_cooling_tower(sw, sl, "East", margin))
    if ct is None:
        print(f"Failed to place Cooling Tower on iteration {i}")
        continue
    placed["Cooling Tower"] = ct
    
    ww = _place_wt_wwt(sw, sl, water[0], water[1], water[2], placed, margin)
    if ww is None:
        print(f"Failed to place WT/WWT on iteration {i}")
        continue
    placed["WT/WWT"] = ww
    
    fl = _try_place_collision_aware(sw, sl, "Flare", placed, lambda: _place_flare(sw, sl, "East", margin))
    if fl is None:
        print(f"Failed to place Flare on iteration {i}")
        continue
    placed["Flare"] = fl
    
    lpg = _try_place_collision_aware(sw, sl, "LPG/Metering", placed, lambda: _place_lpg(sw, sl, margin))
    if lpg is None:
        print(f"Failed to place LPG on iteration {i}")
        continue
    placed["LPG/Metering"] = lpg
    
    wh_x, wh_y, wh_rotated = _place_warehouse(sw, sl, placed, margin)
    placed["Warehouse"] = (wh_x, wh_y, wh_rotated)
    
    if _has_any_overlap(placed):
        print(f"Failed final overlap check on iteration {i}")
        continue
        
    print(f"SUCCESS placing all buildings on iteration {i}!")
    break
