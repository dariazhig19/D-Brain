with open("../../00_Input/Phase_06_Plan_Structured.md", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "wt" in line.lower():
        safe_line = line.strip().encode('ascii', errors='ignore').decode('ascii')
        print(f"Line {i+1}: {safe_line}")
