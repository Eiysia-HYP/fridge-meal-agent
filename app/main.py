from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from . import agent
from .config import BASE_DIR
from .db import init_db
from .services import inventory, memory, recipes

app = FastAPI(title="冰箱食材管家 Agent")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
def _startup() -> None:
    init_db()
    inventory.seed_demo_data()


class ChatRequest(BaseModel):
    sessionId: str | None = None
    message: str = Field(..., min_length=1, max_length=2000)


@app.post("/api/chat")
def chat_endpoint(payload: ChatRequest) -> dict:
    session_id = payload.sessionId or memory.new_session_id()
    result = agent.chat(session_id, payload.message.strip())
    return {"sessionId": session_id, **result}


@app.get("/")
def index() -> RedirectResponse:
    return RedirectResponse("/chat")


@app.get("/chat")
def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


@app.get("/inventory")
def inventory_page(request: Request):
    return templates.TemplateResponse(
        "inventory.html", {"request": request, "items": inventory.list_items()}
    )


@app.post("/inventory/add")
def inventory_add(
    name: str = Form(...), quantity: float = Form(...), unit: str = Form("个")
):
    inventory.add_quantity(name, quantity, unit)
    return RedirectResponse("/inventory", status_code=303)


@app.get("/recipes")
def recipes_page(request: Request, q: str = ""):
    result = {"recipes": [], "source": "", "warning": ""}
    if q.strip():
        result = recipes.search_recipes(q.strip(), limit=6)
    return templates.TemplateResponse(
        "recipes.html", {"request": request, "q": q, **result}
    )
