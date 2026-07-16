"""
数据库连接与会话管理
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

import config
from database.models import Base

engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite 需要
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """创建所有表"""
    Base.metadata.create_all(bind=engine)
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info(persons)")).fetchall()
            columns = [row[1] for row in res]
            if "body_label" not in columns:
                conn.execute(text("ALTER TABLE persons ADD COLUMN body_label VARCHAR(100) DEFAULT ''"))
                conn.commit()
    except Exception as e:
        print(f"Database migration (body_label) failed: {e}")


@contextmanager
def get_db_session():
    """获取数据库会话的上下文管理器"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    """FastAPI 依赖注入用的数据库会话生成器"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
