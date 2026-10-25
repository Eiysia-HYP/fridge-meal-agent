from datetime import datetime, timezone
from typing import Any

from ..db import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_dict(row) -> dict[str, Any]:
    return {
        "name": row["name"],
        "quantity": row["quantity"],
        "unit": row["unit"],
        "expiresOn": row["expires_on"],
        "updatedAt": row["updated_at"],
    }


def list_items(name: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT name, quantity, unit, expires_on, updated_at FROM inventory"
    params: tuple = ()
    if name:
        sql += " WHERE name LIKE ?"
        params = (f"%{name}%",)
    sql += " ORDER BY name"
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_item(name: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT name, quantity, unit, expires_on, updated_at FROM inventory WHERE name = ?",
            (name,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def set_quantity(
    name: str, quantity: float, unit: str = "个", expires_on: str | None = None
) -> dict[str, Any]:
    if not name.strip():
        raise ValueError("食材名称不能为空")
    if quantity < 0:
        raise ValueError("数量不能为负数")
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO inventory(name, quantity, unit, expires_on, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                quantity = excluded.quantity,
                unit = excluded.unit,
                expires_on = COALESCE(excluded.expires_on, inventory.expires_on),
                updated_at = excluded.updated_at
            """,
            (name.strip(), quantity, unit or "个", expires_on, _now()),
        )
    return get_item(name.strip())


def add_quantity(name: str, quantity: float, unit: str = "个") -> dict[str, Any]:
    if quantity <= 0:
        raise ValueError("增加数量必须大于 0")
    current = get_item(name.strip())
    base = current["quantity"] if current else 0
    return set_quantity(name, base + quantity, unit or (current or {}).get("unit", "个"))


def remove_quantity(name: str, quantity: float) -> dict[str, Any]:
    if quantity <= 0:
        raise ValueError("扣减数量必须大于 0")
    current = get_item(name.strip())
    if not current:
        raise ValueError(f"库存中没有「{name}」")
    if current["quantity"] < quantity:
        raise ValueError(
            f"「{name}」库存不足，当前 {current['quantity']}{current['unit']}"
        )
    return set_quantity(name, current["quantity"] - quantity, current["unit"])


def seed_demo_data() -> None:
    if list_items():
        return
    demo = [
        ("鸡蛋", 8, "个"),
        ("西红柿", 3, "个"),
        ("土豆", 4, "个"),
        ("青菜", 1, "把"),
        ("鸡胸肉", 500, "克"),
        ("大米", 2, "千克"),
        ("食用油", 1, "瓶"),
        ("盐", 1, "袋"),
        ("大蒜", 5, "瓣"),
    ]
    for name, qty, unit in demo:
        set_quantity(name, qty, unit)
