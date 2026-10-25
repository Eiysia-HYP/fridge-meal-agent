from app.services import planner


def _recipe(name, ingredients, rid=None):
    return {
        "id": rid or name,
        "name": name,
        "category": "Test",
        "area": "Test",
        "instructions": "Step one. Step two.",
        "ingredients": [{"name": n, "measure": "1"} for n in ingredients],
    }


INVENTORY = [
    {"name": "鸡蛋", "quantity": 6, "unit": "个"},
    {"name": "西红柿", "quantity": 2, "unit": "个"},
]


def test_generate_plan_prefers_available_ingredients():
    recipes = [
        _recipe("西红柿炒蛋", ["鸡蛋", "西红柿"]),
        _recipe("烤鸡", ["鸡腿", "迷迭香"]),
    ]
    plan = planner.generate_meal_plan(recipes, INVENTORY, people=2)
    assert plan["slots"][0]["recipe"]["name"] == "西红柿炒蛋"
    assert plan["slots"][0]["missing"] == []
    assert plan["people"] == 2


def test_avoid_filter_is_hard_constraint():
    recipes = [_recipe("花生鸡", ["鸡肉", "花生"])]
    plan = planner.generate_meal_plan(recipes, INVENTORY, people=2, avoid=["花生"])
    assert plan["slots"] == []
    assert "没有满足条件" in plan["notes"][0]


def test_shopping_list_aggregates_missing_ingredients():
    recipes = [_recipe("清蒸鱼", ["鲈鱼", "姜"])]
    plan = planner.generate_meal_plan(recipes, INVENTORY, people=2)
    names = [i["name"] for i in plan["shoppingList"]]
    assert "鲈鱼" in names
    assert "姜" in names


def test_modify_plan_replaces_only_target_slot():
    recipes = [
        _recipe("西红柿炒蛋", ["鸡蛋", "西红柿"]),
        _recipe("烤鸡", ["鸡腿"]),
        _recipe("蔬菜汤", ["青菜"]),
    ]
    plan = planner.generate_meal_plan(recipes, INVENTORY, people=2)
    target_slot = plan["slots"][0]["slot"]
    new_recipes = [_recipe("清蒸鱼", ["鲈鱼", "姜"], rid="fish")]
    updated = planner.modify_meal_plan(plan, target_slot, new_recipes, INVENTORY)
    assert updated["slots"][0]["recipe"]["name"] == "清蒸鱼"
    assert updated["slots"][1]["recipe"]["name"] == plan["slots"][1]["recipe"]["name"]
