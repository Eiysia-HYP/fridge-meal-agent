from typing import Any

SLOTS = ["主菜", "配菜", "主食或汤"]


def _text_of(recipe: dict[str, Any]) -> str:
    parts = [recipe.get("name") or ""]
    parts += [i.get("name") or "" for i in recipe.get("ingredients", [])]
    return " ".join(parts).lower()


def _contains_avoid(recipe: dict[str, Any], avoid: list[str]) -> bool:
    text = _text_of(recipe)
    return any(a.strip().lower() and a.strip().lower() in text for a in avoid)


def _match_ingredients(
    recipe: dict[str, Any], inventory: dict[str, dict[str, Any]]
) -> tuple[list[dict], list[dict]]:
    have, missing = [], []
    for ing in recipe.get("ingredients", []):
        name = (ing.get("name") or "").strip().lower()
        if not name:
            continue
        hit = None
        for inv_name, item in inventory.items():
            if len(name) >= 2 and len(inv_name) >= 2 and (name in inv_name or inv_name in name):
                hit = item
                break
        if hit and hit["quantity"] > 0:
            have.append(
                {"name": ing["name"], "quantity": hit["quantity"], "unit": hit["unit"]}
            )
        else:
            missing.append({"name": ing["name"], "measure": ing.get("measure") or ""})
    return have, missing


def build_shopping_list(plan: dict[str, Any]) -> list[dict[str, Any]]:
    agg: dict[str, dict[str, Any]] = {}
    for slot in plan.get("slots", []):
        recipe_name = slot["recipe"].get("name", "")
        for miss in slot.get("missing", []):
            key = (miss["name"] or "").strip().lower()
            if not key:
                continue
            if key in agg:
                if recipe_name not in agg[key]["sources"]:
                    agg[key]["sources"].append(recipe_name)
            else:
                agg[key] = {
                    "name": miss["name"],
                    "measure": miss.get("measure") or "",
                    "sources": [recipe_name],
                }
    return list(agg.values())


def _notes(plan: dict[str, Any], people: int, avoid: list[str]) -> list[str]:
    notes = [f"按 {people} 人份安排，用量请按实际食量调整。"]
    if avoid:
        notes.append("已排除忌口食材：" + "、".join(avoid) + "。")
    if plan.get("shoppingList"):
        notes.append(f"共有 {len(plan['shoppingList'])} 种食材需要补买。")
    else:
        notes.append("现有库存基本可以覆盖，无需额外采购。")
    notes.append("菜谱步骤来自外部菜谱服务，实际烹饪请结合厨具和口味调整。")
    return notes


def generate_meal_plan(
    recipes: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
    people: int = 2,
    avoid: list[str] | None = None,
    preference: str | None = None,
) -> dict[str, Any]:
    avoid = [a for a in (avoid or []) if a and a.strip()]
    inv = {i["name"].lower(): i for i in inventory}
    usable = [r for r in recipes if not _contains_avoid(r, avoid)]

    plan: dict[str, Any] = {
        "people": people,
        "avoid": avoid,
        "preference": preference,
        "slots": [],
        "shoppingList": [],
        "notes": [],
    }

    if not usable:
        plan["notes"] = ["没有满足条件的菜谱，请更换关键词或减少忌口后再试。"]
        return plan

    scored = []
    for recipe in usable:
        have, missing = _match_ingredients(recipe, inv)
        scored.append((len(missing), -len(have), recipe, have, missing))
    scored.sort(key=lambda x: (x[0], x[1]))

    seen_ids: set[str] = set()
    picked = []
    for item in scored:
        rid = str(item[2].get("id") or item[2].get("name"))
        if rid in seen_ids:
            continue
        seen_ids.add(rid)
        picked.append(item)
        if len(picked) == len(SLOTS):
            break

    for slot_name, (_, _, recipe, have, missing) in zip(SLOTS, picked):
        plan["slots"].append(
            {
                "slot": slot_name,
                "recipe": {
                    "id": recipe.get("id"),
                    "name": recipe.get("name"),
                    "category": recipe.get("category"),
                    "area": recipe.get("area"),
                },
                "have": have,
                "missing": missing,
                "steps": _short_steps(recipe.get("instructions", "")),
            }
        )

    plan["shoppingList"] = build_shopping_list(plan)
    plan["notes"] = _notes(plan, people, avoid)
    return plan


def _short_steps(instructions: str, limit: int = 5) -> list[str]:
    text = (instructions or "").replace("\r", "\n")
    raw = [seg.strip() for seg in text.split("\n") if seg.strip()]
    if len(raw) <= 1:
        raw = [seg.strip() for seg in text.split(".") if seg.strip()]
    return raw[:limit]


def modify_meal_plan(
    plan: dict[str, Any],
    slot: str,
    new_recipes: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    target = None
    for item in plan.get("slots", []):
        if item["slot"] == slot or item["recipe"].get("name") == slot:
            target = item
            break
    if target is None:
        raise ValueError(f"计划中没有找到「{slot}」，可用时段：主菜 / 配菜 / 主食或汤")

    avoid = plan.get("avoid") or []
    inv = {i["name"].lower(): i for i in inventory}
    candidate = None
    for recipe in new_recipes:
        if _contains_avoid(recipe, avoid):
            continue
        candidate = recipe
        break
    if candidate is None:
        raise ValueError("没有找到满足忌口条件的新菜谱，请换一个关键词")

    have, missing = _match_ingredients(candidate, inv)
    target["recipe"] = {
        "id": candidate.get("id"),
        "name": candidate.get("name"),
        "category": candidate.get("category"),
        "area": candidate.get("area"),
    }
    target["have"] = have
    target["missing"] = missing
    target["steps"] = _short_steps(candidate.get("instructions", ""))

    plan["shoppingList"] = build_shopping_list(plan)
    plan["notes"] = _notes(plan, plan.get("people", 2), avoid)
    return plan
