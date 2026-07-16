import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.chat import ChatSession, ChatMessage
from backend.app.schemas.chat import ChatSessionCreate, ChatSessionResponse, ChatMessageCreate, ChatMessageResponse
from backend.app.services.auth_service import get_current_user
from backend.app.ai.agent_loop import run_agent_loop

router = APIRouter(prefix="/chat", tags=["AI Chatbot"])

@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    session_in: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    title = session_in.title or "محادثة جديدة"
    new_session = ChatSession(
        user_id=current_user.id,
        title=title,
        context_snapshot={}
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return new_session

@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
    )
    return result.scalars().all()

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_chat_history(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify session belongs to user
    session_result = await db.execute(
        select(ChatSession).where(
            and_(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="جلسة المحادثة غير موجودة"
        )
        
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return result.scalars().all()

@router.post("/sessions/{session_id}/messages")
async def send_message_stream(
    session_id: uuid.UUID,
    message_in: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify session belongs to user
    session_result = await db.execute(
        select(ChatSession).where(
            and_(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="جلسة المحادثة غير موجودة"
        )
        
    # Save user message
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=message_in.content,
        tool_metadata={}
    )
    db.add(user_msg)
    await db.commit()
    
    return StreamingResponse(
        run_agent_loop(session.id, message_in.content, current_user.id, db),
        media_type="text/event-stream"
    )
