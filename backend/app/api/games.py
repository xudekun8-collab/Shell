"""游戏接口：开始与提交。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.session import SessionLocal
from app.services import game_engine

router = APIRouter()


class StartRequest(BaseModel):
    user_id: str
    game_type: str


class AnswerItem(BaseModel):
    index: int
    value: bool | str


class SubmitRequest(BaseModel):
    session_id: str
    answers: list[AnswerItem] = []
    duration_sec: int = 0
    abandoned: bool = False


class StartResponse(BaseModel):
    session_id: str
    game_type: str
    difficulty: int
    time_limit_sec: int
    items: dict


class SubmitResponse(BaseModel):
    correct: int
    total: int
    accuracy: float
    next_difficulty: int
    summary_text: str


@router.post("/api/game/start", response_model=StartResponse)
def start_game(request: StartRequest) -> StartResponse:
    with SessionLocal() as db:
        result = game_engine.start(request.user_id, request.game_type, db)
    return StartResponse(**result)


@router.post("/api/game/submit", response_model=SubmitResponse)
def submit_game(request: SubmitRequest) -> SubmitResponse:
    try:
        with SessionLocal() as db:
            result = game_engine.submit(
                request.session_id,
                [a.model_dump() for a in request.answers],
                request.duration_sec,
                request.abandoned,
                db,
            )
    except ValueError:
        raise HTTPException(status_code=404, detail="会话已失效，请重新开始")
    return SubmitResponse(**result)
