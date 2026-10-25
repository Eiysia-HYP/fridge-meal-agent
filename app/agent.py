import json
from typing import Any

from openai import OpenAI

from .config import settings
from .services import memory
from .tools import TOOLS, dispatch

SYSTEM_PROMPT = """你是「冰箱食材管家」智能体，负责帮助用户管理冰箱食材、推荐菜谱、生成晚餐计划和购物清单。

必须遵守的规则：
1. 任何关于库存数量、食材有无的问题，必须先调用 get_inventory，不得凭记忆或猜测回答。
2. 推荐菜谱或生成计划必须先调用 search_recipes / generate_meal_plan，不得编造菜谱或配料。
3. 修改计划使用 modify_meal_plan，只改用户指定的时段，保留其他菜品和条件。
4. add_inventory 和 remove_inventory 属于写操作，必须先用自然语言向用户确认，得到明确同意后才能调用。
5. 工具返回 warning、error 或字段缺失时，如实告知用户，不得编造数据。
6. 用户没有说明人数时，优先使用会话记忆里的人数；仍然没有就按 2 人处理并说明。
7. 回复使用简洁中文，适当使用列表；不要输出工具调用的原始 JSON。"""

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.dashscope_api_key, base_url=settings.dashscope_base_url
        )
    return _client


def _context_text(session: dict[str, Any]) -> str:
    parts = []
    if session.get("people"):
        parts.append(f"当前会话人数：{session['people']}")
    if session.get("avoid"):
        parts.append("忌口：" + "、".join(session["avoid"]))
    if session.get("preference"):
        parts.append(f"偏好：{session['preference']}")
    plan = session.get("lastPlan")
    if plan and plan.get("slots"):
        dishes = "、".join(
            f"{s['slot']}={s['recipe']['name']}" for s in plan["slots"]
        )
        parts.append(f"最近一次计划：{dishes}")
    return "会话记忆：" + "；".join(parts) if parts else ""


def chat(session_id: str, message: str) -> dict[str, Any]:
    if not settings.dashscope_api_key:
        return {
            "reply": "服务端未配置 DASHSCOPE_API_KEY，聊天功能暂不可用。"
                     "你仍然可以使用 /inventory 和 /recipes 页面。",
            "toolTrace": [],
        }

    memory.ensure_session(session_id)
    memory.append_message(session_id, "user", message)

    session = memory.get_session(session_id)
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    ctx = _context_text(session)
    if ctx:
        messages.append({"role": "system", "content": ctx})
    messages.extend(memory.load_messages(session_id, limit=20))

    trace: list[dict[str, Any]] = []

    for _ in range(settings.max_tool_rounds):
        completion = get_client().chat.completions.create(
            model=settings.model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.3,
        )
        msg = completion.choices[0].message

        if not msg.tool_calls:
            reply = (msg.content or "").strip()
            memory.append_message(session_id, "assistant", reply)
            return {"reply": reply, "toolTrace": trace}

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                result = dispatch(tc.function.name, args, session_id)
            except Exception as exc:
                result = {"error": str(exc)}
            trace.append(
                {"name": tc.function.name, "arguments": args, "result": result}
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    fallback = "工具调用次数超过上限，请把问题拆小一点，或先告诉我人数和忌口。"
    memory.append_message(session_id, "assistant", fallback)
    return {"reply": fallback, "toolTrace": trace}
