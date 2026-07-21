"""管理 SQLAlchemy 引擎、会话。"""

import os
import importlib
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DB_PATH, IO

DEFAULT_DB_PATH = DB_PATH


def _resolve_db_url():
    """优先读取配置中的数据库 URL，否则回退到默认 SQLite。"""
    # 1) 环境变量 / 配置项 io.db_url
    cfg_url = (IO.get('db_url') or '').strip()
    if cfg_url:
        return cfg_url
    # 2) SQLite 默认
    return f'sqlite:///{DEFAULT_DB_PATH}'

DB_URL = _resolve_db_url()

# SQLite 需要 check_same_thread=False（Flask 多线程）；其他 DB 默认即可
_engine_kwargs = {}
if DB_URL.startswith('sqlite'):
    os.makedirs(os.path.dirname(DEFAULT_DB_PATH), exist_ok=True)
    _engine_kwargs['connect_args'] = {'check_same_thread': False}
    _engine_kwargs['pool_pre_ping'] = True

engine = create_engine(DB_URL, future=True, **_engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


@contextmanager
def session_scope():
    """提供自动提交或回滚的数据库会话上下文。"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """导入模型并建表。"""
    # 必须在 import models 之后才能 create_all（让 Base.metadata 看到所有表）
    importlib.import_module('.models', __package__)
    Base.metadata.create_all(engine)
