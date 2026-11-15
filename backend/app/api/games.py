"""游戏接口：开始与提交。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_role
from app.db.session import SessionLocal
from app.services import game_engine
from app.services.games import UnknownGameError

router = APIRouter()


class StartRequest(BaseModel):
    game_type: str = Field(min_length=1, max_length=32)
    # 可选：智能体在 plan 节点已经算过档位，直接带过来就用，避免这里重算一遍
    difficulty: int | None = Field(default=None, ge=1, le=3)


class AnswerItem(BaseModel):
    index: int = Field(ge=0, le=50)
    value: bool | str


class SubmitRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=40)
    answers: list[AnswerItem] = Field(default_factory=list, max_length=20)
    duration_sec: int = 0
    abandoned: bool = False


class StartResponse(BaseModel):
    session_id: str
    game_type: str
    difficulty: int
    time_limit_sec: int
    items: dict


class SubmitDetail(BaseModel):
    index: int
    correct: bool
    correct_text: str
    explanation: str


class SubmitResponse(BaseModel):
    correct: int
    total: int
    accuracy: float
    next_difficulty: int
    summary_text: str
    details: list[SubmitDetail]


@router.post("/api/game/start", response_model=StartResponse)
def start_game(request: StartRequest, user: dict = Depends(require_role("elder"))) -> StartResponse:
    try:
        with SessionLocal() as db:
            result = game_engine.start(
                user["user_id"], request.game_type, db, difficulty=request.difficulty
            )
    except UnknownGameError:
        raise HTTPException(status_code=400, detail="未知题型")
    except ValueError:
        raise HTTPException(status_code=400, detail="未知难度")
    return StartResponse(**result)


@router.post("/api/game/submit", response_model=SubmitResponse)
def submit_game(request: SubmitRequest, user: dict = Depends(require_role("elder"))) -> SubmitResponse:
    try:
        with SessionLocal() as db:
            result = game_engine.submit(
                request.session_id,
                [a.model_dump() for a in request.answers],
                request.duration_sec,
                request.abandoned,
                db,
                expect_user_id=user["user_id"],
            )
    except UnknownGameError:
        raise HTTPException(status_code=400, detail="未知题型")
    except PermissionError:
        raise HTTPException(status_code=403, detail="会话不属于当前用户")
    except ValueError:
        raise HTTPException(status_code=404, detail="会话已失效，请重新开始")
    return SubmitResponse(**result)
