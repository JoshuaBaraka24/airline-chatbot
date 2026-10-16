"""Staff dashboard endpoints (FR-06). Every route requires an admin session."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel

from backend import auth, conversation_log, rasa_client

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)])

STATUS_PATTERN = r"^(active|closed|escalated)$"


class Conversation(BaseModel):
    conversation_id: int
    sender_id: str
    start_time: datetime
    end_time: Optional[datetime]
    turn_count: int
    last_intent: Optional[str]
    status: str
    passenger_name: Optional[str]
    passenger_email: Optional[str]


class TranscriptLine(BaseModel):
    speaker: str
    text: str
    timestamp: Optional[float]
    intent: Optional[str] = None


@router.get("/stats")
def stats() -> dict:
    return conversation_log.dashboard_stats()


@router.get("/conversations", response_model=List[Conversation])
def conversations(
    status_filter: Optional[str] = Query(None, alias="status", regex=STATUS_PATTERN),
    limit: int = Query(50, ge=1, le=200),
) -> List[dict]:
    return conversation_log.list_conversations(status_filter, limit)


@router.get("/conversations/{conversation_id}/transcript", response_model=List[TranscriptLine])
def transcript(conversation_id: int = Path(..., ge=1)) -> List[dict]:
    conversation = conversation_log.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    try:
        return rasa_client.transcript(conversation["sender_id"])
    except rasa_client.RasaUnavailableError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Transcript unavailable: the assistant is offline.")


@router.post("/conversations/{conversation_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
def resolve(conversation_id: int = Path(..., ge=1)) -> None:
    if not conversation_log.resolve_conversation(conversation_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only escalated conversations can be resolved.")
