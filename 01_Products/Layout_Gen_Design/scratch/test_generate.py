import sys, random, importlib
sys.path.append('.')
import Core.Layout06 as L
importlib.reload(L)

random.seed(42)
r = L.generate_sketch(500, 270, 'East')

if r:
    print('SUCCESS! Stubs generated for:')
    for name, st in r['stubs'].items():
        print(f"  {name}: ring={len(st['ring_stub'])} pts, peri={len(st['perimeter_stub'])} pts")
else:
    print('FAILED')
