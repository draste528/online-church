from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/chats", tags=["Chat"])

PLACEHOLDER_REPLY = "Ваше сообщение получено. Священник ответит в ближайшее время."


class ChatMessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class ChatMessageOut(BaseModel):
    reply: str


@router.post("/messages", response_model=ChatMessageOut)
async def send_message(message: ChatMessageIn):
    """Accept a message for the priest. Persistence and real replies are not implemented yet."""
    return ChatMessageOut(reply=PLACEHOLDER_REPLY)
