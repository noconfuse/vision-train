"""负责项目目录识别、信息读写与目录生命周期操作。"""

import os
from datetime import datetime

from app.config import PROJECTS_DIR
from contexts.project.domain.policies import PROJECT_DEFAULT_SUBDIRS, PROJECT_RESERVED_NAMES, validate_project_name
from shared.utils.fs_utils import move_path, remove_path_silent
from shared.utils.path_utils import project_name_from_path, project_path_ref


def load_project_info(project_path, datasets=None):
    """读取项目展示所需的基础信息。"""
    try:
        name = project_name_from_path(project_path)
        desc = ""
        desc_path = os.path.join(project_path, ".description")
        if os.path.isfile(desc_path):
            try:
                with open(desc_path, "r", encoding="utf-8") as f:
                    desc = f.read().strip()
            except Exception:
                desc = ""
        return {
            "id": name,
            "name": name,
            "description": desc,
            "created_at": datetime.fromtimestamp(os.path.getctime(project_path)).strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.fromtimestamp(os.path.getmtime(project_path)).strftime("%Y-%m-%d %H:%M:%S"),
            "path": project_path_ref(project_path),
            "datasets": datasets or [],
        }
    except Exception:
        return None


def list_project_paths():
    """枚举项目根目录下受协议管理的项目目录。"""
    if not os.path.isdir(PROJECTS_DIR):
        return []
    project_paths = []
    for item in os.listdir(PROJECTS_DIR):
        if item.startswith(".") or item in PROJECT_RESERVED_NAMES:
            continue
        if validate_project_name(item):
            continue
        project_path = os.path.join(PROJECTS_DIR, item)
        if not os.path.isdir(project_path):
            continue
        project_paths.append(project_path)
    return sorted(project_paths)


def create_project(name, description=""):
    """创建项目目录及默认子目录。"""
    project_path = os.path.join(PROJECTS_DIR, name)
    if os.path.exists(project_path):
        raise ValueError(f"项目 {name} 已存在")
    os.makedirs(project_path)
    for sub in PROJECT_DEFAULT_SUBDIRS:
        os.makedirs(os.path.join(project_path, sub), exist_ok=True)
    if description:
        with open(os.path.join(project_path, ".description"), "w", encoding="utf-8") as f:
            f.write(description)
    return project_path


def update_project(name, description=None, new_name=None):
    """更新项目目录名或描述文件。"""
    project_path = os.path.join(PROJECTS_DIR, name)
    if not os.path.isdir(project_path):
        raise ValueError(f"项目 {name} 不存在")
    target_path = project_path
    if new_name and new_name != name:
        new_path = os.path.join(PROJECTS_DIR, new_name)
        if os.path.exists(new_path):
            raise ValueError(f"目标项目 {new_name} 已存在")
        move_path(project_path, new_path)
        target_path = new_path
    if description is not None:
        with open(os.path.join(target_path, ".description"), "w", encoding="utf-8") as f:
            f.write(description)
    return target_path


def delete_project(name):
    """硬删除项目目录。"""
    project_path = os.path.join(PROJECTS_DIR, name)
    if not os.path.isdir(project_path):
        raise ValueError(f"项目 {name} 不存在")
    remove_path_silent(project_path)
    return {"deleted": name, "mode": "hard"}
