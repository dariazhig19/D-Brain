with open("../../00_Input/2026-05-14 - Session Report.md", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "wt" in line.lower():
        safe_line = line.strip().encode('ascii', errors='ignore').decode('ascii')
        print(f"Line {i+1}: {safe_line}")
