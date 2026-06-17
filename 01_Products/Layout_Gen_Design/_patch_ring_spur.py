import sys, random

with open('Core/Layout06.py', encoding='utf-8') as f:
    content = f.read()

# Markers for the block to replace
start_marker = '            # Ring Spur construction  [-> §3.4.D]'
end_marker   = '                gate_spur = [exit_helper, bb_mid, other_corner, (gate_pt[0], other_corner[1]), gate_pt]'

si = content.find(start_marker)
ei = content.find(end_marker, si) + len(end_marker)

if si < 0: print('START MARKER NOT FOUND'); sys.exit(1)
if ei < len(end_marker): print('END MARKER NOT FOUND'); sys.exit(1)

new_block = (
    '            # Ring Spur construction  [-> §3.4.D]\n'
    '            # Step 1: find the ring road CORNER closest to exit_helper (4 corners, no midpoint)\n'
    '            rxs = [p[0] for p in ring_road]; rys = [p[1] for p in ring_road]\n'
    '            rxmin, rxmax = min(rxs), max(rxs)\n'
    '            rymin, rymax = min(rys), max(rys)\n'
    '            ehx, ehy = exit_helper\n'
    '            ring_corners_all = [\n'
    '                (rxmin, rymin), (rxmax, rymin),\n'
    '                (rxmin, rymax), (rxmax, rymax),\n'
    '            ]\n'
    '            spur_start = min(ring_corners_all,\n'
    '                             key=lambda c: (c[0] - ehx)**2 + (c[1] - ehy)**2)\n'
    '            sx, sy = spur_start\n'
    '\n'
    '            # Step 2: orthogonal L-route from spur_start to exit_helper.\n'
    '            # exit_line axis: horizontal (y=ehy) for N/S boom, vertical (x=ehx) for E/W boom.\n'
    '            # Two L-options — pick randomly:\n'
    '            #   Option A  (project onto exit_line): turn_pt = (sx, ehy) [N/S]  / (ehx, sy) [E/W]\n'
    '            #   Option B  (extend ring road edge):  turn_pt = (ehx, sy) [N/S]  / (sx, ehy) [E/W]\n'
    '            if bb_edge in ("N", "S"):\n'
    '                turn_pt = random.choice([(sx, ehy), (ehx, sy)])\n'
    '            else:\n'
    '                turn_pt = random.choice([(ehx, sy), (sx, ehy)])\n'
    '\n'
    '            # Ring spur: 2 axis-aligned segments — spur_start -> turn_pt -> exit_helper\n'
    '            ring_spur = [spur_start, turn_pt, exit_helper]\n'
    '\n'
    '            # Gate spur: exit_helper -> bb_mid -> other_corner -> Gate  [-> §3.4.B step 4]\n'
    '            if bb_edge in ("N", "S"):\n'
    '                gate_spur = [exit_helper, bb_mid, other_corner, (other_corner[0], gate_pt[1]), gate_pt]\n'
    '            else:\n'
    '                gate_spur = [exit_helper, bb_mid, other_corner, (gate_pt[0], other_corner[1]), gate_pt]'
)

content2 = content[:si] + new_block + content[ei:]
with open('Core/Layout06.py', 'w', encoding='utf-8') as f:
    f.write(content2)

lines_replaced = (content[si:ei].count('\n'))
print(f'OK - replaced {lines_replaced} lines')
