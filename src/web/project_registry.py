#!/usr/bin/env python3
"""
项目注册与选择模块
扫描 models/*/datasets/* 项目，读取数据集配置，提供当前项目与类别信息。
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional

import yaml


# 计算项目根目录（从 src/web/annotation/*.py 向上4级）
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
PROJECTS_DIR = PROJECT_ROOT / "projects"

# 缓存当前项目的存储位置
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CURRENT_PROJECT_FILE = CACHE_DIR / "current_project.json"


def _read_dataset_yaml(dataset_dir: Path, configs_dir: Optional[Path] = None) -> Optional[Dict]:
    candidates: List[Path] = []
    if configs_dir:
        candidates.append(configs_dir / "dataset.yaml")
    candidates.extend([
        dataset_dir / "dataset.yaml",
        dataset_dir / "data.yaml",
        dataset_dir / "train" / "dataset.yaml",
        dataset_dir / "train" / "data.yaml",
    ])
    for cfg in candidates:
        if cfg.exists():
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                # 忽略格式错误，继续尝试其他路径
                pass
    return None


def _classes_from_cfg(cfg: Optional[Dict]) -> Dict[int, str]:
    """从数据集配置构建类别映射，若不可用则回退到 behavior_config."""
    if cfg and isinstance(cfg, dict):
        names = cfg.get("names")
        nc = cfg.get("nc")
        if isinstance(names, list) and (nc is None or nc == len(names)):
            return {i: str(name) for i, name in enumerate(names)}
        # 有些配置 names 可能是 dict
        if isinstance(names, dict):
            # 规范化为从0开始的连续ID
            try:
                items = sorted(((int(k), str(v)) for k, v in names.items()), key=lambda x: x[0])
                return {i: name for i, name in items}
            except Exception:
                pass
    # 回退：使用行为配置中的类别
    try:
        from .behavior_config import BEHAVIOR_CLASSES as DEFAULT_BEHAVIOR_CLASSES
    except Exception:
        DEFAULT_BEHAVIOR_CLASSES = {0: "未知"}
    return {int(k): str(v) for k, v in DEFAULT_BEHAVIOR_CLASSES.items()}


def scan_projects() -> List[Dict]:
    projects: List[Dict] = []
    if not PROJECTS_DIR.exists():
        return projects

    for project_dir in PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue

        datasets_dir = project_dir / "datasets"
        training_dir = project_dir / "training"
        subdirs: List[Path] = []
        if datasets_dir.exists():
            subdirs.extend([d for d in datasets_dir.iterdir() if d.is_dir()])
        if training_dir.exists():
            for d in training_dir.iterdir():
                if d.is_dir() and d.name.startswith("datasets"):
                    subdirs.append(d)

        # 支持 config 或 configs 目录命名
        configs_dir = project_dir / "configs"
        if not configs_dir.exists():
            alt = project_dir / "config"
            configs_dir = alt if alt.exists() else configs_dir

        pretrained_dir = project_dir / "pretrained"
        models_dir = project_dir / "models"

        # 遍历数据集子目录（支持 projects/*/datasets_* 以及 projects/*/datasets/*）
        for dataset_subdir in subdirs:
            if not dataset_subdir.is_dir():
                continue

            train_images_dir = dataset_subdir / "train" / "images"
            train_labels_dir = dataset_subdir / "train" / "labels"
            val_images_dir = dataset_subdir / "val" / "images"
            val_labels_dir = dataset_subdir / "val" / "labels"

            if not train_images_dir.exists():
                continue

            cfg = _read_dataset_yaml(dataset_subdir, configs_dir if configs_dir and configs_dir.exists() else None)
            classes = _classes_from_cfg(cfg)
            nc = len(classes)

            projects.append({
                "id": str(dataset_subdir.resolve()),
                "name": dataset_subdir.name,
                "pretrained_dir": str(pretrained_dir.resolve()) if pretrained_dir.exists() else str(pretrained_dir),
                "models_dir": str(models_dir.resolve()) if models_dir.exists() else str(models_dir),
                "dataset_dir": str(dataset_subdir.resolve()),
                "images_dir": str(train_images_dir.resolve()),
                "labels_dir": str(train_labels_dir.resolve()),
                "val_images_dir": str(val_images_dir.resolve()) if val_images_dir.exists() else None,
                "val_labels_dir": str(val_labels_dir.resolve()) if val_labels_dir.exists() else None,
                "configs_dir": str(configs_dir.resolve()) if configs_dir and configs_dir.exists() else None,
                "classes": classes,
                "nc": nc,
            })
    return projects


def _default_project_id(projects: List[Dict]) -> Optional[str]:
    if not projects:
        return None
    return projects[0]["id"]


def get_current_project() -> Optional[Dict]:
    """获取当前项目，如果未设置则选择默认并保存。"""
    projects = scan_projects()
    if not projects:
        return None
    current_id: Optional[str] = None
    if CURRENT_PROJECT_FILE.exists():
        try:
            with open(CURRENT_PROJECT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                current_id = data.get("id")
        except Exception:
            current_id = None
    if not current_id:
        current_id = _default_project_id(projects)
        if current_id:
            set_current_project(current_id)
    # 返回项目详情
    for p in projects:
        if p["id"] == current_id:
            return p
    # 如果ID不匹配，回退第一个
    return projects[0]


def set_current_project(project_id: str) -> Dict:
    """设置当前项目，并将其写入缓存文件。返回项目详情。"""
    projects = scan_projects()
    target = None
    for p in projects:
        if p["id"] == project_id:
            target = p
            break
    if target is None:
        raise ValueError("项目不存在或不可用")
    with open(CURRENT_PROJECT_FILE, "w", encoding="utf-8") as f:
        json.dump({"id": target["id"]}, f, ensure_ascii=False, indent=2)
    return target


def get_current_classes() -> Dict[int, str]:
    """返回当前项目的类别映射（包含动态类别）"""
    proj = get_current_project()
    if not proj:
        return {}
    
    # 获取预设类别
    base_classes = proj["classes"] if proj else {}
    
    # 加载动态类别（如果存在）
    try:
        from annotator_app import load_dynamic_classes
        dynamic_classes = load_dynamic_classes()
        
        # 处理新格式（包含颜色信息）
        processed_dynamic = {}
        for class_id, class_info in dynamic_classes.items():
            if isinstance(class_info, dict) and 'name' in class_info:
                # 新格式：{id: {'name': name, 'color': color}}
                processed_dynamic[class_id] = class_info['name']
            else:
                # 旧格式：{id: name}
                processed_dynamic[class_id] = str(class_info)
        
        # 合并预设类别和动态类别
        return {**base_classes, **processed_dynamic}
    except ImportError:
        # 如果无法导入load_dynamic_classes，只返回预设类别
        return base_classes
    except Exception as e:
        # 如果加载动态类别失败，记录错误并返回预设类别
        print(f"加载动态类别失败: {e}")
        return base_classes


def get_current_paths() -> Dict[str, str]:
    """返回当前项目相关路径"""
    proj = get_current_project()
    if not proj:
        return {}
    return {
        "models_dir": proj.get("models_dir", ""),
        "dataset_dir": proj.get("dataset_dir", ""),
        "images_dir": proj.get("images_dir", ""),
        "labels_dir": proj.get("labels_dir", ""),
        "val_images_dir": proj.get("val_images_dir", ""),
        "val_labels_dir": proj.get("val_labels_dir", ""),
        "pretrained_dir": proj.get("pretrained_dir", ""),
        "configs_dir": proj.get("configs_dir", ""),
    }
