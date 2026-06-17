import json
import os
import glob

app_data_dir = r"C:\Users\상상진화\.gemini\antigravity-ide\brain"
transcript_paths = glob.glob(os.path.join(app_data_dir, "*", ".system_generated", "logs", "transcript.jsonl"))

print(f"Found {len(transcript_paths)} transcripts")
for path in transcript_paths:
    print(f"\nSearching {path}...")
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if "flare" in line.lower():
                try:
                    obj = json.loads(line)
                    content = obj.get("content", "")
                    if content:
                        print(f"  Line {i} content: {content[:400]}")
                    tool_calls = obj.get("tool_calls", [])
                    for tc in tool_calls:
                        args = tc.get("arguments", "")
                        if args and "flare" in str(args).lower():
                            print(f"  Line {i} tool call {tc.get('name')}: {str(args)[:400]}")
                except Exception as e:
                    pass
