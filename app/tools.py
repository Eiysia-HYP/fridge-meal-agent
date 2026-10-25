import json
from typing import Any

from .services import inventory, memory, planner, recipes

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_inventory",
            "description": "查询冰箱库存。name 可选，传入食材名做模糊过滤。",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "食材名称，可省略"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_inventory",
            "description": "向库存增加食材。属于写操作，必须先得到用户明确同意。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit": {"type": "string"},
                },
                "required": ["name", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_inventory",
            "description": "从库存扣减食材。属于写操作，必须先得到用户明确同意。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": "number"},
                },
                "required": ["name", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_recipes",
            "description": "调用 TheMealDB 搜索菜谱，返回菜名、配料和简要步骤。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "菜名或主要食材，如 chicken / egg / tomato"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_meal_plan",
            "description": "结合库存、人数、忌口和偏好生成一顿饭的计划，并自动生成购物清单。",
            "parameters": {
                "type": "object",
                "properties": {
                    "people": {"type": "integer", "default": 2},
                    "avoid": {"type": "array", "items": {"type": "string"}},
                    "preference": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modify_meal_plan",
            "description": "修改当前会话最近一次计划中的某个时段，保留其他菜品和条件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "slot": {"type": "string", "description": "主菜 / 配菜 / 主食或汤，也可以传菜名"},
                    "keyword": {"type": "string", "description": "新菜搜索关键词，如 fish / beef"},
                },
                "required": ["slot", "keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_shopping_list",
            "description": "根据当前会话最近一次计划与库存差额生成购物清单。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _default_keywords(session: dict[str, Any]) -> list[str]:
    items = inventory.list_items()
    if items:
        return [items[0]["name"], "vegetable"]
    return ["chicken"]


def _collect_recipes(keywords: list[str], limit: int = 5) -> tuple[list[dict], list[str]]:
    collected, warnings, seen = [], [], set()
    for kw in keywords:
        result = recipes.search_recipes(kw, limit=limit)
        if result.get("warning"):
            warnings.append(result["warning"])
        for recipe in result.get("recipes", []):
            rid = str(recipe.get("id") or recipe.get("name"))
            if rid in seen:
                continue
            seen.add(rid)
            collected.append(recipe)
    return collected, warnings


def dispatch(name: str, args: dict[str, Any], session_id: str) -> dict[str, Any]:
    session = memory.get_session(session_id)

    if name == "get_inventory":
        return {"items": inventory.list_items(args.get("name"))}

    if name == "add_inventory":
        item = inventory.add_quantity(
            args["name"], float(args["quantity"]), args.get("unit") or "个"
        )
        return {"ok": True, "item": item}

    if name == "remove_inventory":
        item = inventory.remove_quantity(args["name"], float(args["quantity"]))
        return {"ok": True, "item": item}

    if name == "search_recipes":
        return recipes.search_recipes(args["keyword"], int(args.get("limit", 5)))

    if name == "generate_meal_plan":
        people = int(args.get("people") or session.get("people") or 2)
        avoid = args.get("avoid") if args.get("avoid") is not None else session.get("avoid", [])
        preference = args.get("preference") or session.get("preference")
        keywords = args.get("keywords") or _default_keywords(session)

        found, warnings = _collect_recipes(keywords)
        plan = planner.generate_meal_plan(
            found, inventory.list_items(), people, avoid, preference
        )
        plan["recipeSource"] = "TheMealDB"
        if warnings:
            plan["warnings"] = warnings
        memory.update_session(
            session_id,
            people=people,
            avoid=avoid,
            preference=preference,
            lastPlan=plan,
            lastShoppingList=plan.get("shoppingList"),
        )
        return plan

    if name == "modify_meal_plan":
        last_plan = session.get("lastPlan")
        if not last_plan:
            return {"error": "当前会话还没有计划，请先生成计划再修改。"}
        found, warnings = _collect_recipes([args["keyword"]])
        try:
            plan = planner.modify_meal_plan(
                last_plan, args["slot"], found, inventory.list_items()
            )
        except ValueError as exc:
            return {"error": str(exc)}
        plan["recipeSource"] = "TheMealDB"
        if warnings:
            plan["warnings"] = warnings
        memory.update_session(session_id, lastPlan=plan, lastShoppingList=plan.get("shoppingList"))
        return plan

    if name == "generate_shopping_list":
        last_plan = session.get("lastPlan")
        if not last_plan:
            return {"error": "当前会话还没有计划，请先生成计划。"}
        items = planner.build_shopping_list(last_plan)
        memory.update_session(session_id, lastShoppingList=items)
        return {"items": items}

    return {"error": f"未知工具：{name}"}


def tool_result_to_text(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False)
