"""定义任务、工作流与认证相关的 ORM 模型。"""

import uuid

from sqlalchemy import (
    Column, String, Integer, Float, Text, ForeignKey, Index, JSON, Boolean
)
from sqlalchemy.orm import relationship

from .session import Base
from shared.utils.time_utils import now_iso
from task_status import TASK_STATUS_PENDING


def _new_id():
    """生成 12 位十六进制主键。"""
    return uuid.uuid4().hex[:12]


class Task(Base):
    """后台任务（训练 / 抽帧 / 自动标注…）。"""
    __tablename__ = 'tasks'

    id = Column(String(12), primary_key=True, default=_new_id)
    type = Column(String(32), nullable=False)              # training / frame_extraction / auto_annotation / ...
    workflow_id = Column(String(12), nullable=True, index=True)
    workflow_type = Column(String(32), nullable=True, index=True)

    # 业务上下文用冗余字段（filesystem 路径用于恢复执行）
    project_path = Column(String(512), nullable=False)
    project_name = Column(String(128), nullable=True, index=True)
    dataset_name = Column(String(128), nullable=True, index=True)
    dataset_path = Column(String(512), nullable=True)

    status = Column(String(16), nullable=False, default=TASK_STATUS_PENDING, index=True)
    progress = Column(Integer, nullable=False, default=0)
    message = Column(String(512), nullable=True)
    error = Column(Text, nullable=True)

    payload = Column(JSON, nullable=True)        # 训练参数 / 抽帧配置
    artifacts = Column(JSON, nullable=True)      # run_id / output_dir / log_path
    log_text = Column(Text, nullable=True)

    created_at = Column(String(32), nullable=False, default=now_iso)
    updated_at = Column(String(32), nullable=False, default=now_iso, index=True)
    started_at = Column(String(32), nullable=True)
    finished_at = Column(String(32), nullable=True)
    archived_at = Column(String(32), nullable=True, index=True)

    history = relationship('TaskHistory', back_populates='task',
                           cascade='all, delete-orphan',
                           order_by='TaskHistory.epoch')

    __table_args__ = (
        Index('idx_task_project_status', 'project_path', 'status'),
        Index('idx_task_dataset_status', 'project_name', 'dataset_name', 'status'),
        Index('idx_task_type_status', 'type', 'status'),
    )

    def to_dict(self):
        """把任务模型转换为接口输出字典。"""
        return {
            'id': self.id,
            'type': self.type,
            'workflow_id': self.workflow_id,
            'workflow_type': self.workflow_type,
            'project_path': self.project_path,
            'project_name': self.project_name,
            'dataset_name': self.dataset_name,
            'dataset_path': self.dataset_path,
            'status': self.status,
            'progress': self.progress or 0,
            'message': self.message,
            'error': self.error,
            'payload': self.payload or {},
            'artifacts': self.artifacts or {},
            'log': (self.log_text or '').splitlines() if self.log_text else [],
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'started_at': self.started_at,
            'finished_at': self.finished_at,
            'archived_at': self.archived_at,
            'is_archived': bool(self.archived_at),
        }


class WorkflowRecord(Base):
    """用户侧工作流记录。"""
    __tablename__ = 'workflow_records'

    id = Column(String(12), primary_key=True, default=_new_id)
    type = Column(String(32), nullable=False, index=True)
    project_path = Column(String(512), nullable=False)
    project_name = Column(String(128), nullable=True, index=True)
    dataset_name = Column(String(128), nullable=True, index=True)
    dataset_path = Column(String(512), nullable=True)
    created_at = Column(String(32), nullable=False, default=now_iso)
    updated_at = Column(String(32), nullable=False, default=now_iso, index=True)
    archived_at = Column(String(32), nullable=True, index=True)

    __table_args__ = (
        Index('idx_workflow_project_type', 'project_path', 'type'),
        Index('idx_workflow_dataset_type', 'project_name', 'dataset_name', 'type'),
    )

    def to_dict(self):
        """把工作流记录转换为接口输出字典。"""
        return {
            'id': self.id,
            'type': self.type,
            'project_path': self.project_path,
            'project_name': self.project_name,
            'dataset_name': self.dataset_name,
            'dataset_path': self.dataset_path,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'archived_at': self.archived_at,
            'is_archived': bool(self.archived_at),
        }


class TaskHistory(Base):
    """训练任务的每个 epoch 指标点（训练曲线）。"""
    __tablename__ = 'task_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(12), ForeignKey('tasks.id', ondelete='CASCADE'),
                     nullable=False, index=True)
    epoch = Column(Integer, nullable=False)
    box_loss = Column(Float, nullable=True)
    cls_loss = Column(Float, nullable=True)
    dfl_loss = Column(Float, nullable=True)
    map50 = Column(Float, nullable=True)
    map50_95 = Column(Float, nullable=True)
    extra_json = Column(JSON, nullable=True)
    created_at = Column(String(32), nullable=False, default=now_iso)

    task = relationship('Task', back_populates='history')

    def to_dict(self):
        """把训练历史点转换为接口输出字典。"""
        return {
            'task_id': self.task_id,
            'epoch': self.epoch,
            'box_loss': self.box_loss,
            'cls_loss': self.cls_loss,
            'dfl_loss': self.dfl_loss,
            'map50': self.map50,
            'map50_95': self.map50_95,
            'created_at': self.created_at,
        }


# ============================================================================
# 认证
# ============================================================================

class User(Base):
    """登录用户。密码用 PBKDF2-HMAC-SHA256 哈希存 password_hash。

    字段：
        id           12 位字符串
        username     唯一、3~32 字符
        email        可空
        password_hash  哈希后的密码
        role         'admin' | 'user'
        is_active    软删标志
        created_at / last_login_at
    """
    __tablename__ = 'users'

    id = Column(String(12), primary_key=True, default=_new_id)
    username = Column(String(64), nullable=False, unique=True, index=True)
    email = Column(String(128), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False, default='user')  # admin / user
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(String(32), nullable=False, default=now_iso)
    last_login_at = Column(String(32), nullable=True)

    sessions = relationship('AuthSession', back_populates='user',
                            cascade='all, delete-orphan')

    def to_dict(self):
        """把用户模型转换为接口输出字典。"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'last_login_at': self.last_login_at,
        }


class AuthSession(Base):
    """登录会话（token 表）。

    设计要点：
        - 不存 JWT 在前端靠签名；服务端存 token 明文，可以吊销（删表行）
        - expires_at 由 auth.session_ttl_seconds 决定
        - revoked=True 即失效
    """
    __tablename__ = 'auth_sessions'

    id = Column(String(12), primary_key=True, default=_new_id)
    user_id = Column(String(12), ForeignKey('users.id', ondelete='CASCADE'),
                     nullable=False, index=True)
    token = Column(String(128), nullable=False, unique=True, index=True)
    created_at = Column(String(32), nullable=False, default=now_iso)
    expires_at = Column(String(32), nullable=False, index=True)
    last_seen_at = Column(String(32), nullable=True)
    ip = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)
    revoked = Column(Boolean, nullable=False, default=False)

    user = relationship('User', back_populates='sessions')

    def to_dict(self):
        """把登录会话转换为接口输出字典。"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
            'last_seen_at': self.last_seen_at,
            'ip': self.ip,
            'user_agent': self.user_agent,
            'revoked': self.revoked,
        }
