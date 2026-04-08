"""Evolution Manager: tracks diagnosis->fix outcomes, promotes proven recipes."""
from __future__ import annotations

import re
from datetime import datetime, UTC
from pathlib import Path

from overmind.diagnosis.judge import Diagnosis
from overmind.evolution.recipe import Recipe


TABLE_ROW_RE = re.compile(
    r"^\| ([^|]+)\| ([^|]+)\| ([^|]+)\| (\d+)\s*\| (\d+)\s*\| (\d+)%\s*\| ([^|]+)\|",
    re.MULTILINE,
)


class EvolutionManager:
    def __init__(self, wiki_dir: Path) -> None:
        self.wiki_dir = wiki_dir
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        self.procedures_path = self.wiki_dir / "PROCEDURES.md"

    def evolve(
        self,
        diagnoses: list[Diagnosis],
        last_night_diagnoses: list[Diagnosis] | None = None,
        resolved_project_ids: set[str] | None = None,
    ) -> dict:
        """Run one evolution cycle. Returns summary stats."""
        recipes = self._load_recipes()
        resolved_project_ids = resolved_project_ids or set()
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")

        new_recipes = 0
        updated_recipes = 0
        resolutions = 0

        # Step 1: Check resolutions — last night's failures that are now passing
        if last_night_diagnoses:
            for diag in last_night_diagnoses:
                if diag.project_id in resolved_project_ids:
                    recipe = self._find_recipe(recipes, diag.failure_type, diag.evidence)
                    if recipe:
                        recipe.record_resolved()
                        resolutions += 1
                        updated_recipes += 1

        # Step 2: Process tonight's diagnoses
        for diag in diagnoses:
            existing = self._find_recipe(recipes, diag.failure_type, diag.evidence)
            if existing:
                existing.record_seen(date_str)
                updated_recipes += 1
            else:
                recipe_id = f"{diag.failure_type}:{_extract_key(diag)}"
                recipe = Recipe(
                    recipe_id=recipe_id,
                    failure_type=diag.failure_type,
                    pattern=_extract_pattern(diag),
                    fix_description=diag.recommended_action,
                    times_seen=1,
                    example_project=diag.project_id[:20],
                    last_seen=date_str,
                    first_seen=date_str,
                )
                recipes.append(recipe)
                new_recipes += 1

        # Step 3: Write PROCEDURES.md
        self._write_procedures(recipes)

        return {
            "total_recipes": len(recipes),
            "new_recipes": new_recipes,
            "updated_recipes": updated_recipes,
            "resolutions": resolutions,
            "proven_recipes": sum(1 for r in recipes if r.is_proven()),
        }

    def get_recommendation(self, diagnosis: Diagnosis) -> Recipe | None:
        """Find a proven recipe for a diagnosis."""
        recipes = self._load_recipes()
        match = self._find_recipe(recipes, diagnosis.failure_type, diagnosis.evidence)
        if match and match.is_proven():
            return match
        return None

    def _find_recipe(self, recipes: list[Recipe], failure_type: str, evidence: list[str]) -> Recipe | None:
        """Find matching recipe by failure type and pattern overlap."""
        for recipe in recipes:
            if recipe.failure_type != failure_type:
                continue
            # Check if any evidence matches the recipe pattern
            for ev in evidence:
                if recipe.pattern and recipe.pattern.lower() in ev.lower():
                    return recipe
            # Fallback: match by failure_type alone if pattern is generic
            if recipe.pattern in ("", "unknown"):
                return recipe
        return None

    def _load_recipes(self) -> list[Recipe]:
        """Parse recipes from PROCEDURES.md."""
        if not self.procedures_path.exists():
            return []
        content = self.procedures_path.read_text(encoding="utf-8")
        recipes = []
        for match in TABLE_ROW_RE.finditer(content):
            recipe_id = match.group(1).strip()
            pattern = match.group(2).strip()
            fix = match.group(3).strip()
            seen = int(match.group(4).strip())
            resolved = int(match.group(5).strip())
            confidence_pct = int(match.group(6).strip())
            last_seen = match.group(7).strip()

            # Extract failure_type from recipe_id (e.g., "DEPENDENCY_ROT:scipy" -> "DEPENDENCY_ROT")
            failure_type = recipe_id.split(":")[0] if ":" in recipe_id else recipe_id

            recipes.append(Recipe(
                recipe_id=recipe_id,
                failure_type=failure_type,
                pattern=pattern,
                fix_description=fix,
                times_seen=seen,
                times_resolved=resolved,
                confidence=confidence_pct / 100.0,
                last_seen=last_seen,
                first_seen=last_seen,  # Not tracked in table — use last_seen
            ))
        return recipes

    def _write_procedures(self, recipes: list[Recipe]) -> None:
        """Write recipes to PROCEDURES.md, sorted by confidence descending."""
        recipes.sort(key=lambda r: (-r.confidence, -r.times_seen, r.recipe_id))
        lines = [
            "# Overmind Procedures",
            "",
            "Automatically discovered fix recipes from nightly verification outcomes.",
            "",
            "| Recipe | Pattern | Fix | Seen | Resolved | Confidence | Last Seen |",
            "|--------|---------|-----|------|----------|------------|-----------|",
        ]
        for r in recipes:
            conf_pct = int(r.confidence * 100)
            lines.append(
                f"| {r.recipe_id} | {r.pattern} | {r.fix_description[:60]} | {r.times_seen} | {r.times_resolved} | {conf_pct}% | {r.last_seen} |"
            )
        lines.append("")
        self.procedures_path.write_text("\n".join(lines), encoding="utf-8")


def _extract_key(diag: Diagnosis) -> str:
    """Extract a short key from diagnosis evidence for recipe_id."""
    if diag.evidence:
        text = diag.evidence[0].lower()
        # Try to find module name
        mod = re.search(r"no module named ['\"]?(\w+)", text)
        if mod:
            return mod.group(1)
        # Try to find variable name from drift
        var = re.search(r"(\w+):\s*[\d.]+\s*->", text)
        if var:
            return var.group(1)
    return diag.project_id[:10]


def _extract_pattern(diag: Diagnosis) -> str:
    """Extract a reusable pattern string from diagnosis evidence."""
    if diag.failure_type == "DEPENDENCY_ROT":
        mod = re.search(r"No module named ['\"]?(\w[\w.]*)", " ".join(diag.evidence))
        if mod:
            return mod.group(1)
    if diag.failure_type == "NUMERICAL_DRIFT":
        var = re.search(r"(\w+):\s*[\d.]+\s*->", " ".join(diag.evidence))
        if var:
            return var.group(1)
    if diag.failure_type == "TIMEOUT":
        return "timed out"
    if diag.evidence:
        # Use first 30 chars of evidence as pattern
        return diag.evidence[0][:30].strip()
    return "unknown"
