"""Plain-python checks. Run before wiring the server to a client."""
import json
from pathlib import Path
from catalog import Catalog

c = Catalog(Path(__file__).parent / "modules")
print(f"loaded {len(c.modules)} modules\n")
print("search 'prompt':", json.dumps(c.search("prompt"), indent=1)[:400], "\n")
print("get crm-210 teaches:", c.get("crm-210")["teaches"], "\n")
g = c.find_gaps(["Prompt Writing", "output verification", "agent building", "evaluation"])
print("gaps:", json.dumps({k: g[k] for k in ("covered", "partial", "uncovered")}, indent=1), "\n")
print("sequence:", json.dumps(c.suggest_sequence("prompt-library-design", "seller", include_draft=True), indent=1), "\n")
print("unreachable:", json.dumps(c.suggest_sequence("agent-building"), indent=1))