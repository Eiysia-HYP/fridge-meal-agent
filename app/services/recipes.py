import json
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import settings
from ..db import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _cache_get(key: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT payload FROM recipes_cache WHERE key = ?", (key,)
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["payload"])
    except json.JSONDecodeError:
        return None


def _cache_set(key: str, payload: dict[str, Any]) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO recipes_cache(key, payload, fetched_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET payload = excluded.payload,
                                           fetched_at = excluded.fetched_at
            """,
            (key, json.dumps(payload, ensure_ascii=False), _now()),
        )


def _normalize_meal(meal: dict[str, Any]) -> dict[str, Any]:
    ingredients = []
    for i in range(1, 21):
        name = (meal.get(f"strIngredient{i}") or "").strip()
        measure = (meal.get(f"strMeasure{i}") or "").strip()
        if name:
            ingredients.append({"name": name, "measure": measure})
    return {
        "id": meal.get("idMeal"),
        "name": meal.get("strMeal"),
        "category": meal.get("strCategory"),
        "area": meal.get("strArea"),
        "instructions": (meal.get("strInstructions") or "").strip(),
        "ingredients": ingredients,
    }


def _fetch(client: httpx.Client, keyword: str, limit: int) -> list[dict[str, Any]]:
    resp = client.get(f"{settings.mealdb_base_url}/search.php", params={"s": keyword})
    resp.raise_for_status()
    meals = resp.json().get("meals") or []

    if not meals:
        resp = client.get(f"{settings.mealdb_base_url}/filter.php", params={"i": keyword})
        resp.raise_for_status()
        briefs = (resp.json().get("meals") or [])[:limit]
        meals = []
        for brief in briefs:
            detail = client.get(
                f"{settings.mealdb_base_url}/lookup.php", params={"i": brief["idMeal"]}
            )
            detail.raise_for_status()
            meals.extend(detail.json().get("meals") or [])

    return [_normalize_meal(m) for m in meals][:limit]


def search_recipes(keyword: str, limit: int = 5) -> dict[str, Any]:
    keyword = (keyword or "").strip()
    if not keyword:
        return {"source": "none", "recipes": [], "warning": "缺少菜谱搜索关键词"}

    key = f"search:{keyword.lower()}:{limit}"
    try:
        with httpx.Client(timeout=settings.http_timeout) as client:
            recipes = _fetch(client, keyword, limit)
        payload = {"source": "TheMealDB", "recipes": recipes}
        if recipes:
            _cache_set(key, payload)
        return payload
    except Exception as exc:
        cached = _cache_get(key)
        if cached:
            result = dict(cached)
            result["source"] = "cache"
            result["warning"] = f"外部菜谱接口不可用，已使用缓存：{exc}"
            return result
        return {
            "source": "none",
            "recipes": [],
            "warning": f"外部菜谱接口不可用且无缓存：{exc}",
        }
