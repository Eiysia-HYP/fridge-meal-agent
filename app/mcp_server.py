"""独立启动的 MCP Server：python -m app.mcp_server"""

from fastmcp import FastMCP

from .services import inventory, planner, recipes

mcp = FastMCP("fridge-meal-agent")


@mcp.tool()
def get_inventory(name: str | None = None) -> list[dict]:
    """查询冰箱库存，name 可选，用于模糊过滤食材名。"""
    return inventory.list_items(name)


@mcp.tool()
def add_inventory(name: str, quantity: float, unit: str = "个") -> dict:
    """增加库存。属于写操作，调用前应先获得用户确认。"""
    return inventory.add_quantity(name, quantity, unit)


@mcp.tool()
def remove_inventory(name: str, quantity: float) -> dict:
    """扣减库存。属于写操作，调用前应先获得用户确认。"""
    return inventory.remove_quantity(name, quantity)


@mcp.tool()
def search_recipes(keyword: str, limit: int = 5) -> dict:
    """调用 TheMealDB 搜索菜谱，失败时自动降级到本地缓存。"""
    return recipes.search_recipes(keyword, limit)


@mcp.tool()
def generate_meal_plan(
    keywords: list[str],
    people: int = 2,
    avoid: list[str] | None = None,
    preference: str | None = None,
) -> dict:
    """结合库存和菜谱生成一顿饭的计划，并附带购物清单。"""
    found, warnings = [], []
    for kw in keywords:
        result = recipes.search_recipes(kw, limit=5)
        if result.get("warning"):
            warnings.append(result["warning"])
        found.extend(result.get("recipes", []))
    plan = planner.generate_meal_plan(
        found, inventory.list_items(), people, avoid or [], preference
    )
    if warnings:
        plan["warnings"] = warnings
    return plan


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8001)
