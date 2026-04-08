# Evolution Manager Design Spec

**Date:** 2026-04-07
**Status:** APPROVED
**Phase:** 4 of Overmind v4

## 1. Purpose

Distills successful diagnosis→fix pairs into procedural memory (recipes). When the same failure pattern recurs, the system recommends the proven fix instead of re-diagnosing from scratch. Replaces the generic heuristic memories with actionable procedures.

## 2. Architecture

```
nightly_verify.py
  └── After judge diagnoses, call:
      EvolutionManager.evolve(diagnoses, previous_recipes)
        ├── Match new diagnoses against existing recipes
        ├── Track resolution: was last night's diagnosis fixed tonight?
        ├── Promote confirmed fix to recipe if pattern seen ≥2 times
        └── Write recipes to wiki/PROCEDURES.md
```

### Files
- Create: `overmind/evolution/__init__.py`
- Create: `overmind/evolution/manager.py` — EvolutionManager class
- Create: `overmind/evolution/recipe.py` — Recipe model
- Modify: `scripts/nightly_verify.py` — call evolution manager after judge
- Test: `C:\OvermindTestBed\tests\test_evolution.py`

## 3. Recipe Model

```python
@dataclass
class Recipe:
    recipe_id: str
    failure_type: str         # From taxonomy (DEPENDENCY_ROT, TIMEOUT, etc.)
    pattern: str              # Regex or keyword that triggers this recipe
    fix_description: str      # Human-readable fix
    times_seen: int           # How many times this pattern occurred
    times_resolved: int       # How many times it was fixed by next run
    confidence: float         # times_resolved / times_seen
    last_seen: str
    first_seen: str
    example_project: str      # First project where this was seen
```

## 4. Evolution Logic

Each nightly run:

1. **Load existing recipes** from `wiki/PROCEDURES.md` (parsed from Markdown table)
2. **Check last night's diagnoses** — for each REJECT/FAIL from last night that is now CERTIFIED/PASS:
   - Find the matching recipe by failure_type + pattern
   - Increment `times_resolved`
   - Update confidence
3. **For tonight's new diagnoses** — match against existing recipes:
   - If match found: increment `times_seen`, recommend the known fix
   - If no match: create a new recipe candidate (times_seen=1, confidence=0)
4. **Promote recipes** — if times_seen ≥ 2 and confidence > 0, recipe is "proven"
5. **Write PROCEDURES.md** — sorted by confidence descending

## 5. PROCEDURES.md Format

```markdown
# Overmind Procedures

Automatically discovered fix recipes from nightly verification outcomes.

| Recipe | Pattern | Fix | Seen | Resolved | Confidence | Last Seen |
|--------|---------|-----|------|----------|------------|-----------|
| DEPENDENCY_ROT:scipy | ImportError.*scipy | `pip install scipy` or check Python 3.13 WMI deadlock | 5 | 3 | 60% | 2026-04-08 |
| TIMEOUT:wmi_deadlock | timed out.*scipy | Monkey-patch `platform._wmi_query` before scipy import | 3 | 2 | 67% | 2026-04-07 |
```

## 6. Integration with Judge

Judge produces Diagnosis objects. Evolution Manager:
- Reads tonight's diagnoses
- Reads last night's diagnoses (from wiki article Notes)
- Compares: if last night's FAIL is tonight's PASS → the fix worked → update recipe

## 7. Testing

| Test | What it proves |
|------|----------------|
| test_new_diagnosis_creates_candidate | First-time failure creates recipe with times_seen=1 |
| test_repeated_pattern_increments | Same failure type twice → times_seen=2 |
| test_resolution_tracked | FAIL→PASS transition increments times_resolved |
| test_confidence_calculated | times_resolved/times_seen = correct ratio |
| test_procedures_md_written | PROCEDURES.md contains recipe table |
| test_recipe_recommended_on_match | Known recipe returned when pattern matches |

6 tests. Combined with 87 = **93 total**.

## 8. Constraints
- No LLM calls — pattern matching + statistics
- Recipes stored as Markdown (human-readable, git-versioned)
- Never auto-apply fixes — only recommend
- Minimum 2 occurrences before recipe is "proven"
- Confidence decays if pattern seen but not resolved (times_seen increases, confidence drops)
