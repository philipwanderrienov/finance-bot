import importlib
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

module = importlib.import_module("backend.services.api.app")
result = module.main()
print(result)
