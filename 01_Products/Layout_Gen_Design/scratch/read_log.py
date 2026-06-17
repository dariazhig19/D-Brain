import os
log_dir = r"C:\Users\상상진화\.gemini\antigravity-ide\brain\7965ee2e-21ab-4623-944d-d0ccd5a37209\.system_generated\tasks"
log_file = os.path.join(log_dir, "task-3643.log")
if os.path.exists(log_file):
    with open(log_file, "r", encoding="utf-8") as f:
        print(f.read())
else:
    print("Log file does not exist yet.")
