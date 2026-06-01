with open("Core/Layout06.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "wt" in line.lower():
        print(f"Line {i+1}: {line.strip()}")
