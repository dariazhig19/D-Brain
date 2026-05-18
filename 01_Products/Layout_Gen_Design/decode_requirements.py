import openpyxl

file_path = r"x:\CST본부 (구 기술지원부 폴더)\15. 다리아\D-Brain\01_Products\Layout_Gen_Design\Data\Plot plan requirement.xlsx"
wb = openpyxl.load_workbook(file_path, data_only=True)
sheet = wb['Layout']

out_lines = []
out_lines.append("# Detailed Layout Requirements\n")
out_lines.append("| Block Name | No | Description | Requirement |")
out_lines.append("| --- | --- | --- | --- |")

for r in range(3, sheet.max_row + 1):
    row_vals = [cell.value for cell in sheet[r]]
    if len(row_vals) >= 5 and (row_vals[1] is not None or row_vals[3] is not None):
        block_cat = str(row_vals[1]) if row_vals[1] is not None else ""
        num = str(row_vals[2]) if row_vals[2] is not None else ""
        desc = str(row_vals[3]) if row_vals[3] is not None else ""
        req = str(row_vals[4]) if row_vals[4] is not None else ""
        # Clean up newlines for markdown table
        req_clean = req.replace('\n', '<br>')
        out_lines.append(f"| {block_cat} | {num} | {desc} | {req_clean} |")

with open("Layout_Requirements.md", "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines))

print("Layout_Requirements.md written successfully in UTF-8!")
