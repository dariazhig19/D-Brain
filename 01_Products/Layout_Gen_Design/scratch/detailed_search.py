import json
import os
import glob

app_data_dir = r"C:\Users\상상진화\.gemini\antigravity-ide\brain"
transcript_paths = glob.glob(os.path.join(app_data_dir, "*", ".system_generated", "logs", "transcript.jsonl"))

for path in transcript_paths:
    if "7965ee2e-21ab-4623-944d-d0ccd5a37209" not in path:
        continue
    print(f"\nSearching {path}...")
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if "flare" in line.lower() or "c-2" in line.lower() or "pipe rack" in line.lower():
                try:
                    obj = json.loads(line)
                    content = obj.get("content", "")
                    if content:
                        print(f"  Line {i} content: {content[:800]}")
                        print("-" * 50)
                except Exception as e:
                    pass
