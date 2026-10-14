"""FastAPI gateway between the chat widget and the Rasa server.

Run from the project root:
    uvicorn backend.main:app --port 8000

Endpoints
    POST /api/chat                  send a message, receive the bot's replies
    POST /api/chat/{sender_id}/end  close a conversation
    GET  /api/health                status of the API, Rasa and the database
    GET  /                          the chat widget (frontend/)
Interactive API docs are served at /docs.
"""
import logging
import time
import uuid
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Path, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator

from backend import conversation_log, rasa_client
from backend.config import ALLOWED_ORIGINS, FRONTEND_DIR, MAX_MESSAGE_LENGTH

logger = logging.getLogger("backend")

UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

app = FastAPI(
    title="Kenya Airways Virtual Assistant API",
    description="REST gateway connecting the chat widget to the Rasa NLU and dialogue engine.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# The widget only loads its own scripts and styles and only calls this API.
# Swagger UI (/docs) loads assets from a CDN, so it is left out.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'"
)
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if not request.url.path.startswith(_DOCS_PATHS):
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    return response


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    # Session token issued by this API on the first message; omit it to start a new conversation.
    sender_id: Optional[str] = Field(None, regex=UUID_PATTERN)

    @validator("message")
    def message_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value


class Button(BaseModel):
    title: str
    payload: str


class BotMessage(BaseModel):
    text: Optional[str] = None
    buttons: List[Button] = []


class ChatResponse(BaseModel):
    sender_id: str
    messages: List[BotMessage]
    response_time_ms: int


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    started = time.perf_counter()
    sender_id = request.sender_id or str(uuid.uuid4())

    try:
        replies = rasa_client.send_message(sender_id, request.message)
    except rasa_client.RasaUnavailableError:
        logger.exception("Rasa server unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The assistant is temporarily unavailable. Please try again shortly.",
        )

    try:
        conversation_log.record_turn(sender_id, rasa_client.latest_intent(sender_id))
    except Exception:
        logger.exception("Could not log turn for %s", sender_id)

    messages = [
        BotMessage(text=reply.get("text"), buttons=reply.get("buttons", []))
        for reply in replies
        if reply.get("text") or reply.get("buttons")
    ]
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return ChatResponse(sender_id=sender_id, messages=messages, response_time_ms=elapsed_ms)


@app.post("/api/chat/{sender_id}/end", status_code=status.HTTP_204_NO_CONTENT)
def end_chat(sender_id: str = Path(..., regex=UUID_PATTERN)) -> None:
    try:
        conversation_log.close_conversation(sender_id)
    except Exception:
        logger.exception("Could not close conversation %s", sender_id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not close the conversation.")


@app.get("/api/health")
def health() -> JSONResponse:
    try:
        conversation_log.check_database()
        database_ok = True
    except Exception:
        database_ok = False
    rasa_ok = rasa_client.is_healthy()
    healthy = database_ok and rasa_ok
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ok" if healthy else "degraded",
            "rasa": "up" if rasa_ok else "down",
            "database": "up" if database_ok else "down",
        },
    )


# Registered last so the API routes above take precedence
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
