"""初始化数据库：建表并写入演示用户。"""
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.models import Base, Profile, User


def init_db(engine: Engine) -> None:
    """在给定引擎上建表，并保证演示用户存在。"""
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        if session.get(User, "demo_user_1") is None:
            session.add(User(id="demo_user_1"))
        if session.get(Profile, "demo_user_1") is None:
            session.add(
                Profile(
                    user_id="demo_user_1",
                    nickname="张阿姨",
                    interests=["黄梅戏", "养花"],
                    taboos=["不要提去世的老伴"],
                )
            )
        session.commit()


if __name__ == "__main__":
    from app.db.session import engine

    init_db(engine)
    print("数据库初始化完成")
