from __future__ import annotations

import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from catalog import Catalog, CatalogError

MODULES_DIR = Path(os.environ.get("CURRICULUM_DIR", Path(__file__).parent / "modules"))

mcp = MCPServer("curriculum-gap")

_catalog: Catalog | None = None


def get_catalog() -> Catalog:
    global _catalog
    if _catalog is None:
        _catalog = Catalog(MODULES_DIR)
    return _catalog


@mcp.tool()
def search_modules(query: str, audience: str = "", limit: int = 5) -> dict:
    """Find training modules matching a topic or skill.

    Args:
        query: Topic, skill, or keyword, e.g. "prompt writing" or "CRM".
        audience: Optional filter, e.g. "seller" or "sales-manager".
        limit: Maximum results to return.
    """
    try:
        results = get_catalog().search(query, audience or None, limit)
    except CatalogError as exc:
        return {"error": str(exc)}
    if not results:
        return {"results": [], "note": "No modules matched. Try a broader term."}
    return {"results": results, "count": len(results)}


@mcp.tool()
def get_module(module_id: str) -> dict:
    """Return the full record for one module, including prerequisites and skills.

    Args:
        module_id: The module id, e.g. "prompt-220".
    """
    try:
        return get_catalog().get(module_id)
    except CatalogError as exc:
        return {"error": str(exc)}


if __name__ == "__main__":
    mcp.run()

@mcp.tool()
def suggest_sequence(goal_skill: str, audience: str = "", include_draft: bool = False) -> dict:
    """Return an ordered learning path that ends at a target skill.

    Prerequisites are resolved first, then modules are ordered by level and
    duration. Returns resolved=false with a reason when no module teaches the
    goal skill.

    Args:
        goal_skill: The skill the learner needs to end up with.
        audience: Optional audience to flag off-audience modules in the path.
        include_draft: Allow draft modules in the path.
    """
    try:
        return get_catalog().suggest_sequence(goal_skill, audience or None, include_draft)
    except CatalogError as exc:
        return {"error": str(exc)}