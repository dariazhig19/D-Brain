import json
import os

transcript_path = r"C:\Users\상상진화\.gemini\antigravity-ide\brain\7965ee2e-21ab-4623-944d-d0ccd5a37209\.system_generated\logs\transcript.jsonl"

words = ["delete", "remove", "along", "path", "buffer"]
print("Searching yesterday's transcript for keywords...")
with open(transcript_path, "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        line_lower = line.lower()
        if any(w in line_lower for w in words) and "flare" in line_lower:
            try:
                obj = json.loads(line)
                content = obj.get("content", "")
                source = obj.get("source", "")
                step_type = obj.get("type", "")
                if source == "USER_EXPLICIT" or step_type == "USER_INPUT":
                    print(f"[Line {i}] USER INPUT: {content}")
                    print("="*80)
                elif source == "MODEL" and step_type == "PLANNER_RESPONSE":
                    print(f"[Line {i}] MODEL RESPONSE: {content[:400]}")
                    print("="*80)
            except Exception as e:
                pass
