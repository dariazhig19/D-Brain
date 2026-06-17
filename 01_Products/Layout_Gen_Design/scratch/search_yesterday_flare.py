import json
import os

transcript_path = r"C:\Users\상상진화\.gemini\antigravity-ide\brain\7965ee2e-21ab-4623-944d-d0ccd5a37209\.system_generated\logs\transcript.jsonl"

print("Searching yesterday's transcript...")
with open(transcript_path, "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "flare" in line.lower():
            try:
                obj = json.loads(line)
                content = obj.get("content", "")
                source = obj.get("source", "")
                step_type = obj.get("type", "")
                # We want to print user messages, model thoughts, and file edits
                if source == "USER_EXPLICIT" or step_type == "USER_INPUT":
                    print(f"[Line {i}] USER INPUT: {content}")
                    print("="*80)
                elif "replace_file_content" in str(obj.get("tool_calls", [])):
                    for tc in obj.get("tool_calls", []):
                        if tc.get("name") == "replace_file_content" or tc.get("name") == "multi_replace_file_content":
                            args = tc.get("arguments", {})
                            if "flare" in str(args).lower():
                                print(f"[Line {i}] FILE EDIT in {args.get('TargetFile')}:")
                                print(args.get("Instruction"))
                                print("="*80)
            except Exception as e:
                pass
