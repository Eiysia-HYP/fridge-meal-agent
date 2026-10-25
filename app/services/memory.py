import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import settings
from ..db import get_db


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def new_session_id() -> str:
    return uuid.uuid4().hex


def ensure_session(session_id: str) -> dict[str, Any]:
    now = _now()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO sessions(id, created_at, updated_at) VALUES (?, ?, ?)",
                (session_id, _iso(now), _iso(now)),
            )
            return {"id": session_id, "people": None, "avoid": [], "preference": None,
                    "lastPlan": None, "lastShoppingList": None}

        updated = datetime.fromisoformat(row["updated_at"])
        if now - updated > timedelta(minutes=settings.session_ttl_minutes):
            conn.execute(
                "UPDATE sessions SET people = NULL, avoid = NULL, preference = NULL, "
                "last_plan = NULL, last_shopping_list = NULL, updated_at = ? WHERE id = ?",
                (_iso(now), session_id),
            )
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()

    return _row_to_session(row)


def _row_to_session(row) -> dict[str, Any]:
    def _load(value):
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    return {
        "id": row["id"],
        "people": row["people"],
        "avoid": _load(row["avoid"]) or [],
        "preference": row["preference"],
        "lastPlan": _load(row["last_plan"]),
        "lastShoppingList": _load(row["last_shopping_list"]),
    }


def get_session(session_id: str) -> dict[str, Any]:
    return ensure_session(session_id)


def update_session(session_id: str, **fields: Any) -> dict[str, Any]:
    ensure_session(session_id)
    mapping = {
        "people": "people",
        "preference": "preference",
    }
    sets, params = ["updated_at = ?"], [_iso(_now())]
    for key, column in mapping.items():
        if key in fields:
            sets.append(f"{column} = ?")
            params.append(fields[key])
    if "avoid" in fields:
        sets.append("avoid = ?")
        params.append(json.dumps(fields["avoid"] or [], ensure_ascii=False))
    if "lastPlan" in fields:
        sets.append("last_plan = ?")
        params.append(json.dumps(fields["lastPlan"], ensure_ascii=False) if fields["lastPlan"] else None)
    if "lastShoppingList" in fields:
        sets.append("last_shopping_list = ?")
        params.append(
            json.dumps(fields["lastShoppingList"], ensure_ascii=False)
            if fields["lastShoppingList"]
            else None
        )
    params.append(session_id)
    with get_db() as conn:
        conn.execute(f"UPDATE sessions SET {', '.join(sets)} WHERE id = ?", tuple(params))
    return get_session(session_id)


def append_message(session_id: str, role: str, content: str) -> None:
    ensure_session(session_id)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, _iso(_now())),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (_iso(_now()), session_id)
        )


def load_messages(session_id: str, limit: int = 20) -> list[dict[str, str]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
