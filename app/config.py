import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    dashscope_base_url: str = os.getenv(
        "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    model: str = os.getenv("DASHSCOPE_MODEL", "qwen-plus")

    db_path: str = os.getenv("DB_PATH", str(BASE_DIR / "data" / "fridge.db"))
    session_ttl_minutes: int = int(os.getenv("SESSION_TTL_MINUTES", "30"))
    max_tool_rounds: int = int(os.getenv("MAX_TOOL_ROUNDS", "6"))

    mealdb_base_url: str = os.getenv(
        "MEALDB_BASE_URL", "https://www.themealdb.com/api/json/v1/1"
    )
    http_timeout: float = float(os.getenv("HTTP_TIMEOUT", "8"))

    mcp_endpoint: str = os.getenv("MCP_ENDPOINT", "")


settings = Settings()
