from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

LEVEL_ORDER = {"foundation": 0, "practitioner": 1, "advanced": 2}
REQUIRED_FIELDS = ("id", "title", "level", "teaches")


class CatalogError(Exception):
    """Raised when the module folder cannot be loaded."""


def normalize_skill(raw: str) -> str:
    slug = raw.strip().lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return re.sub(r"-{2,}", "-", slug).strip("-")


@dataclass
class Module:
    id: str
    title: str
    description: str
    level: str
    audience: list[str] = field(default_factory=list)
    duration_minutes: int | None = None
    teaches: list[str] = field(default_factory=list)
    touches: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    format: str = "elearning"
    status: str = "published"
    source_file: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "level": self.level,
            "audience": self.audience,
            "duration_minutes": self.duration_minutes,
            "teaches": self.teaches,
            "touches": self.touches,
            "prerequisites": self.prerequisites,
            "format": self.format,
            "status": self.status,
        }


def _parse_module(path: Path) -> Module:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise CatalogError(f"{path.name}: missing YAML frontmatter. Add a '---' block at the top.")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise CatalogError(f"{path.name}: frontmatter is not closed. Add a second '---' line.")

    meta = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()

    missing = [f for f in REQUIRED_FIELDS if not meta.get(f)]
    if missing:
        raise CatalogError(f"{path.name}: missing required field(s): {', '.join(missing)}")

    level = str(meta["level"]).strip().lower()
    if level not in LEVEL_ORDER:
        raise CatalogError(f"{path.name}: level '{level}' is not one of {', '.join(LEVEL_ORDER)}")

    return Module(
        id=str(meta["id"]).strip(),
        title=str(meta["title"]).strip(),
        description=body,
        level=level,
        audience=[str(a).strip().lower() for a in meta.get("audience", [])],
        duration_minutes=meta.get("duration_minutes"),
        teaches=[normalize_skill(s) for s in meta.get("teaches", [])],
        touches=[normalize_skill(s) for s in meta.get("touches", [])],
        prerequisites=[str(p).strip() for p in meta.get("prerequisites", [])],
        format=str(meta.get("format", "elearning")).strip().lower(),
        status=str(meta.get("status", "published")).strip().lower(),
        source_file=path.name,
    )


class Catalog:
    def __init__(self, folder: Path):
        self.folder = folder
        self.modules: dict[str, Module] = {}
        self.load()

    def load(self) -> None:
        if not self.folder.is_dir():
            raise CatalogError(f"Module folder not found: {self.folder}")
        found: dict[str, Module] = {}
        for path in sorted(self.folder.glob("*.md")):
            module = _parse_module(path)
            if module.id in found:
                raise CatalogError(
                    f"Duplicate module id '{module.id}' in {path.name} "
                    f"and {found[module.id].source_file}"
                )
            found[module.id] = module
        if not found:
            raise CatalogError(f"No .md modules found in {self.folder}")

        for module in found.values():
            for prereq in module.prerequisites:
                if prereq not in found:
                    raise CatalogError(
                        f"{module.source_file}: prerequisite '{prereq}' does not exist"
                    )
        self.modules = found

    def get(self, module_id: str) -> dict:
        module = self.modules.get(module_id.strip())
        if module is None:
            close = [m for m in self.modules if module_id.strip().lower() in m.lower()]
            hint = f" Did you mean: {', '.join(close)}?" if close else ""
            raise CatalogError(f"No module with id '{module_id}'.{hint}")
        return module.as_dict()

    def search(self, query: str, audience: str | None = None, limit: int = 5) -> list[dict]:
        terms = [t for t in normalize_skill(query).split("-") if t]
        if not terms:
            return []
        results = []
        for module in self.modules.values():
            if audience and normalize_skill(audience) not in module.audience:
                continue
            score = 0
            haystacks = {
                3: module.title.lower(),
                2: " ".join(module.teaches + module.touches),
                1: module.description.lower(),
            }
            matched = []
            for weight, hay in haystacks.items():
                for term in terms:
                    if term in hay:
                        score += weight
                        matched.append(term)
            if score:
                results.append({
                    "id": module.id,
                    "title": module.title,
                    "level": module.level,
                    "audience": module.audience,
                    "teaches": module.teaches,
                    "score": score,
                    "matched_terms": sorted(set(matched)),
                })
        results.sort(key=lambda r: (-r["score"], r["id"]))
        return results[:limit]

    def find_gaps(self, skills: list[str], include_draft: bool = False) -> dict:
        live = [m for m in self.modules.values()
                if include_draft or m.status == "published"]
        taught: dict[str, list[str]] = {}
        touched: dict[str, list[str]] = {}
        for module in live:
            for skill in module.teaches:
                taught.setdefault(skill, []).append(module.id)
            for skill in module.touches:
                touched.setdefault(skill, []).append(module.id)

        covered, partial, uncovered = [], [], []
        for raw in skills:
            skill = normalize_skill(raw)
            if not skill:
                continue
            if skill in taught:
                covered.append({"skill": skill, "taught_by": sorted(taught[skill])})
            elif skill in touched:
                partial.append({
                    "skill": skill,
                    "touched_by": sorted(touched[skill]),
                    "note": "Mentioned as secondary content only. No module has this as a learning objective.",
                })
            else:
                uncovered.append({"skill": skill, "note": "Not present anywhere in the catalog."})

        return {
            "requested": len(skills),
            "covered": covered,
            "partial": partial,
            "uncovered": uncovered,
            "other_skills_in_catalog": sorted(
                (set(taught) | set(touched)) - {normalize_skill(s) for s in skills}
            ),
            "draft_modules_included": include_draft,
        }

    def suggest_sequence(self, goal_skill: str, audience: str | None = None,
                         include_draft: bool = False) -> dict:
        goal = normalize_skill(goal_skill)
        live = {m.id: m for m in self.modules.values()
                if include_draft or m.status == "published"}

        targets = [m for m in live.values() if goal in m.teaches]
        if not targets:
            touched_by = [m.id for m in live.values() if goal in m.touches]
            return {
                "goal_skill": goal,
                "path": [],
                "resolved": False,
                "reason": (
                    f"No module teaches '{goal}'."
                    + (f" It is touched on in: {', '.join(sorted(touched_by))}." if touched_by else "")
                    + " This is a catalog gap, not a query error."
                ),
            }

        needed: set[str] = set()
        stack = [t.id for t in targets]
        missing_prereqs: set[str] = set()
        while stack:
            mid = stack.pop()
            if mid in needed:
                continue
            needed.add(mid)
            for prereq in live[mid].prerequisites if mid in live else []:
                if prereq not in live:
                    missing_prereqs.add(prereq)
                    continue
                stack.append(prereq)

        remaining = {m: set(p for p in live[m].prerequisites if p in needed) for m in needed}
        ordered: list[str] = []
        while remaining:
            ready = [m for m, deps in remaining.items() if not deps]
            if not ready:
                return {
                    "goal_skill": goal,
                    "path": [],
                    "resolved": False,
                    "reason": ("Prerequisite cycle detected among: " + ", ".join(sorted(remaining))
                               + ". Fix the prerequisites in those module files."),
                }
            ready.sort(key=lambda m: (LEVEL_ORDER[live[m].level],
                                      live[m].duration_minutes or 9999, m))
            pick = ready[0]
            ordered.append(pick)
            del remaining[pick]
            for deps in remaining.values():
                deps.discard(pick)

        path = [{
            "step": i + 1,
            "id": mid,
            "title": live[mid].title,
            "level": live[mid].level,
            "duration_minutes": live[mid].duration_minutes,
            "reason": "teaches the goal skill" if goal in live[mid].teaches else "prerequisite",
        } for i, mid in enumerate(ordered)]

        warnings = []
        if audience:
            aud = normalize_skill(audience)
            off = [p["id"] for p in path if aud not in live[p["id"]].audience]
            if off:
                warnings.append(f"Not written for audience '{aud}': {', '.join(sorted(off))}. "
                                "Included because they are required prerequisites.")
        if missing_prereqs:
            warnings.append("Prerequisites excluded because they are draft or missing: "
                            + ", ".join(sorted(missing_prereqs)))

        return {
            "goal_skill": goal,
            "path": path,
            "total_minutes": sum(live[p["id"]].duration_minutes or 0 for p in path),
            "resolved": True,
            "warnings": warnings,
        }