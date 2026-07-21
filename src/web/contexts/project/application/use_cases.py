"""编排项目列表、创建、更新、删除与名称校验用例。"""

import os

from app.config import PROJECTS_DIR
from contexts.dataset.application.use_cases import list_project_datasets
from contexts.project.domain.policies import validate_project_name
from contexts.project.infrastructure.project_repository import (
    create_project as repo_create_project,
    delete_project as repo_delete_project,
    list_project_paths,
    load_project_info,
    update_project as repo_update_project,
)


def list_projects():
    """聚合项目基础信息与数据集列表。"""
    projects = []
    for project_path in list_project_paths():
        datasets = list_project_datasets(project_path)
        info = load_project_info(project_path, datasets=datasets)
        if info:
            projects.append(info)
    return projects


def create_project(name, description=""):
    """校验参数后创建项目并返回详情。"""
    err = validate_project_name(name)
    if err:
        raise ValueError(err)
    project_path = repo_create_project(name, description or "")
    return load_project_info(project_path, datasets=[])


def update_project(name, description=None, new_name=None):
    """更新项目并返回最新详情。"""
    err = validate_project_name(name)
    if err:
        raise ValueError(f"原项目名不合法: {err}")
    if new_name and new_name != name:
        err = validate_project_name(new_name)
        if err:
            raise ValueError(f"新项目名不合法: {err}")
    project_path = repo_update_project(name, description=description, new_name=new_name)
    datasets = list_project_datasets(project_path)
    return load_project_info(project_path, datasets=datasets)


def delete_project(name, confirm=False):
    """在确认后删除指定项目。"""
    err = validate_project_name(name)
    if err:
        raise ValueError(err)
    if not confirm:
        raise ValueError("需要 confirm=true 确认删除")
    return repo_delete_project(name)


def validate_project_name_availability(name):
    """校验项目名规则并检查目录冲突。"""
    err = validate_project_name(name)
    if err:
        return {"valid": False, "reason": err}
    if os.path.exists(os.path.join(PROJECTS_DIR, name)):
        return {"valid": False, "reason": f"项目 {name} 已存在"}
    return {"valid": True}
