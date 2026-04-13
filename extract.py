import os
import re

log_path = r"C:\Users\LEE_HWAJIN03\.gemini\antigravity\brain\20b8a22f-a135-48b9-a9b4-365a12fc7701\.system_generated\logs\overview.txt"
with open(log_path, "r", encoding="utf-8") as f:
    text = f.read()

# </div>\n</div>\n\n<div class="modal-overlay" ~ </body>\n</html> 부분까지 매칭
match = re.search(r'(<!DOCTYPE html>.*?</html>)', text, re.IGNORECASE | re.DOTALL)
if match:
    os.makedirs("ui", exist_ok=True)
    with open(r"ui\dashboard_template.html", "w", encoding="utf-8") as f:
        f.write(match.group(1))
    print("HTML extracted and saved successfully!")
else:
    print("HTML NOT FOUND!")
