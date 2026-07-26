"""对话接口：前端智能助手 <-> 后端能力的桥梁。"""
from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.langgraph_chat import (
    handle_chat, resume_chat, get_pending_interrupt, get_history, stream_chat_events,
)
from fastapi.responses import StreamingResponse

router = APIRouter()


class ChatMessage(BaseModel):
    role: str = 'user'
    text: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    place: Optional[str] = None
    passenger: Optional[str] = None
    session_id: Optional[str] = None   # 用于 Checkpointer 区分会话（缺省用 passenger）
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    intent: Optional[str] = 'general'
    flights: List[dict] = []
    reviews: List[dict] = []
    hotels: List[dict] = []
    place: Optional[str] = None
    confirm: Optional[Any] = None
    escalated: bool = False          # CompleteOrEscalate：是否转交主助手/人工
    handoff: Optional[dict] = None    # 结构化交还信息 {action, reason, target}


class ResumeRequest(BaseModel):
    session_id: str
    approved: bool


@router.post('/chat', response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    result = await handle_chat(req.model_dump())
    return ChatResponse(**result)


@router.post('/chat/stream')
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """节点级 SSE 流式对话：边跑图边推送进度/文本事件，避免前端因长时间零字节而超时。"""
    return StreamingResponse(
        stream_chat_events(req.model_dump()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 关闭反向代理（如 nginx）缓冲，保证 SSE 实时下发
        },
    )


@router.post('/chat/resume', response_model=ChatResponse)
async def chat_resume(req: ResumeRequest) -> ChatResponse:
    """恢复被 interrupt 挂起的敏感操作（human-in-the-loop 的 approve/拒绝分支）。"""
    result = await resume_chat(req.session_id, req.approved)
    return ChatResponse(**result)


@router.get('/chat/pending')
async def chat_pending(session_id: str):
    """查看该会话当前是否被中断（待人工确认），用于前端重连后恢复确认框。"""
    from app.services.langgraph_chat import APPROVAL_PROMPT

    payload = await get_pending_interrupt(session_id)
    return {
        "interrupted": bool(payload),
        "payload": payload,
        "resume_reply": (payload or {}).get("prompt", APPROVAL_PROMPT),
    }


@router.get('/chat/history/{session_id}')
async def chat_history(session_id: str):
    """返回该会话已持久化的聊天记录，前端刷新页面后调用以恢复对话。"""
    return {"messages": await get_history(session_id)}
