from pathlib import Path
import re

text = Path("shared/config.py").read_text(encoding="utf-8")
match = re.search(r'postgresql://[^"\']+', text)
print(match.group(0) if match else "NO_MATCH")
