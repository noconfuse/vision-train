"""管理 SQLAlchemy 引擎、会话与轻量 schema 补齐。"""

import os
import logging
import importlib
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DB_PATH, IO

logger = logging.getLogger(__name__)

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
    """导入模型、建表并执行轻量 schema 补齐。"""
    # 必须在 import models 之后才能 create_all（让 Base.metadata 看到所有表）
    importlib.import_module('.models', __package__)
    Base.metadata.create_all(engine)
    _ensure_schema_updates()
    logger.info('数据库已就绪: %s', DB_URL)


def _ensure_schema_updates():
    """为缺少迁移的旧库补齐关键字段与回填逻辑。"""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if 'tasks' not in table_names:
        return

    task_columns = {col['name'] for col in inspector.get_columns('tasks')}
    if 'archived_at' not in task_columns:
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE tasks ADD COLUMN archived_at VARCHAR(32)'))
        logger.info('数据库 schema 已补充: tasks.archived_at')
    if 'workflow_id' not in task_columns:
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE tasks ADD COLUMN workflow_id VARCHAR(12)'))
        logger.info('数据库 schema 已补充: tasks.workflow_id')
    if 'workflow_type' not in task_columns:
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE tasks ADD COLUMN workflow_type VARCHAR(32)'))
        logger.info('数据库 schema 已补充: tasks.workflow_type')
    if 'workflow_records' in table_names:
        workflow_columns = {col['name'] for col in inspector.get_columns('workflow_records')}
        if 'archived_at' not in workflow_columns:
            with engine.begin() as conn:
                conn.execute(text('ALTER TABLE workflow_records ADD COLUMN archived_at VARCHAR(32)'))
            logger.info('数据库 schema 已补充: workflow_records.archived_at')
        _backfill_training_workflows()


def _backfill_training_workflows():
    """为历史 training 任务补建缺失的工作流记录。"""
    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT DISTINCT
                COALESCE(workflow_id, id) AS workflow_id,
                project_path,
                project_name,
                dataset_name,
                dataset_path,
                MIN(created_at) AS created_at,
                MAX(updated_at) AS updated_at
            FROM tasks
            WHERE type = 'training'
            GROUP BY COALESCE(workflow_id, id), project_path, project_name, dataset_name, dataset_path
        """)).mappings().all()
        for row in rows:
            conn.execute(text("""
                INSERT OR IGNORE INTO workflow_records (
                    id, type, project_path, project_name, dataset_name, dataset_path, created_at, updated_at, archived_at
                ) VALUES (
                    :id, 'training', :project_path, :project_name, :dataset_name, :dataset_path, :created_at, :updated_at, NULL
                )
            """), {
                'id': row['workflow_id'],
                'project_path': row['project_path'],
                'project_name': row['project_name'],
                'dataset_name': row['dataset_name'],
                'dataset_path': row['dataset_path'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
            })
