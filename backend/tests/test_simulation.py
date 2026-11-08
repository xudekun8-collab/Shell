"""模拟用户实验台测试。"""
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.init_db import init_db
from app.db.models import TrainingRecord
from scripts.sim_users import GAMES_PER_MODEL, MODELS, QUESTION_COUNT, run_simulation

ROOT = Path(__file__).resolve().parent.parent
FIG_PATHS = [
    ROOT / "data" / "figs" / "fig1_ablation.png",
    ROOT / "data" / "figs" / "fig2_adaptive.png",
    ROOT / "data" / "figs" / "fig3_training.png",
]


def _fresh():
    engine = create_engine("sqlite://")
    init_db(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_reproducible():
    a = run_simulation(42, _fresh())["trajectories"]
    b = run_simulation(42, _fresh())["trajectories"]
    assert a == b


def test_convergence_levels():
    result = run_simulation(20261108, _fresh())
    assert result["models"]["strong"]["final_difficulty"] == 3
    assert result["models"]["weak"]["final_difficulty"] == 1


def test_record_count_and_total():
    factory = _fresh()
    run_simulation(20261108, factory)
    with factory() as db:
        rows = db.execute(select(TrainingRecord)).scalars().all()
    assert len(rows) == GAMES_PER_MODEL * len(MODELS)
    for r in rows:
        assert r.total_count == QUESTION_COUNT[r.difficulty]


@pytest.mark.skipif(
    not all(p.exists() for p in FIG_PATHS),
    reason="图未生成，先运行 scripts/make_figures.py",
)
def test_figures_exist():
    for p in FIG_PATHS:
        assert p.stat().st_size > 10240
