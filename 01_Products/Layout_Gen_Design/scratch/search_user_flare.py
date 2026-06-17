import json
import os
import glob

app_data_dir = r"C:\Users\상상진화\.gemini\antigravity-ide\brain"
transcript_paths = glob.glob(os.path.join(app_data_dir, "*", ".system_generated", "logs", "transcript.jsonl"))

for path in transcript_paths:
    print(f"\nSearching {path}...")
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            try:
                obj = json.loads(line)
                if obj.get("type") == "USER_INPUT" and "flare" in obj.get("content", "").lower():
                    print(f"  Line {i} USER_INPUT:")
                    print(obj.get("content"))
                    print("=" * 60)
            except Exception as e:
                pass
