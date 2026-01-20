import os
import sys
import yaml
from ultralytics import YOLO

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from managers.training_manager import TrainingManager

# Constants
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PRETRAINED_MODELS_DIR = os.path.join(PROJECT_ROOT, "pretrained_models")

# 缓存加载的模型
_light_models = {}

class ModelManager:
    """模型管理器"""
    
    @staticmethod
    def get_global_pretrained_models():
        """获取全局预训练模型"""
        models = []
        config_file = os.path.join(PRETRAINED_MODELS_DIR, "config.yaml")
        
        # 1. 从 config.yaml 读取配置
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    cfg = yaml.safe_load(f) or {}
                    confs = cfg.get('pretrained_models') or {}
                    if isinstance(confs, dict):
                        for key, item in confs.items():
                            name = item.get('name') or key
                            path = item.get('path')
                            if path:
                                if not os.path.isabs(path):
                                    path = os.path.join(PROJECT_ROOT, path)
                                if os.path.exists(path):
                                    models.append({
                                        "name": name,
                                        "type": "pretrained",
                                        "path": os.path.abspath(path),
                                        "size": os.path.getsize(path) if os.path.isfile(path) else 0,
                                        "is_global": True
                                    })
            except Exception as e:
                print(f"Error loading pretrained models config: {e}")

        # 2. 扫描 pretrained_models 目录下的 .pt 文件
        if os.path.exists(PRETRAINED_MODELS_DIR):
            for entry in os.listdir(PRETRAINED_MODELS_DIR):
                ep = os.path.join(PRETRAINED_MODELS_DIR, entry)
                if os.path.isfile(ep) and entry.lower().endswith('.pt'):
                    # 避免重复添加 (通过路径判断)
                    existing_paths = {m['path'] for m in models}
                    if os.path.abspath(ep) not in existing_paths:
                        models.append({
                            "name": entry,
                            "type": "pretrained",
                            "path": os.path.abspath(ep),
                            "size": os.path.getsize(ep),
                            "is_global": True
                        })
        return models

    @staticmethod
    def scan_models(project_path):
        """扫描项目下的模型"""
        models = []
        
        # 0. 添加全局预训练模型
        models.extend(ModelManager.get_global_pretrained_models())

        # 1. 扫描 models 目录（预训练模型或导入的模型）
        models_dir = os.path.join(project_path, "models")
        if os.path.exists(models_dir):
            for item in os.listdir(models_dir):
                if item.lower().endswith('.pt'):
                    models.append({
                        "name": item,
                        "type": "pretrained",
                        "path": os.path.join(models_dir, item),
                        "size": os.path.getsize(os.path.join(models_dir, item))
                    })
                    
        # 2. 扫描 training_outputs (训练产物)
        runs = TrainingManager.list_training_runs(project_path)
        for run in runs:
            # best.pt
            best_pt = os.path.join(run['path'], 'weights', 'best.pt')
            if os.path.exists(best_pt):
                models.append({
                    "name": f"{run['dataset']}_{run['id']}_best.pt",
                    "type": "trained",
                    "path": best_pt,
                    "size": os.path.getsize(best_pt),
                    "source_run": run['id']
                })
            # last.pt
            last_pt = os.path.join(run['path'], 'weights', 'last.pt')
            if os.path.exists(last_pt):
                 models.append({
                    "name": f"{run['dataset']}_{run['id']}_last.pt",
                    "type": "trained",
                    "path": last_pt,
                    "size": os.path.getsize(last_pt),
                    "source_run": run['id']
                })
                
        return models

    @staticmethod
    def get_model_info(model_path):
        """获取模型信息"""
        try:
            model = YOLO(model_path)
            return {
                "names": model.names,
                "task": model.task
            }
        except Exception:
            return None

    @staticmethod
    def get_auto_annotate_model(project_path=None, prefer_project_best=True):
        """获取用于自动标注的模型"""
        global _light_models
        
        # 优先使用项目最新训练权重
        if prefer_project_best and project_path:
            arts = TrainingManager.get_latest_artifacts(project_path)
            w = arts.get('weights_best') or arts.get('weights_last')
            if w and os.path.exists(w):
                key = f"best:{w}"
                m = _light_models.get(key)
                if m is None:
                    try:
                        m = YOLO(w)
                        _light_models[key] = m
                    except:
                        pass
                if m:
                    return m
                    
        # 备用轻量模型
        key = 'yolo11n'
        m = _light_models.get(key)
        if m is None:
            try:
                # 交由 Ultralytics 自动下载
                m = YOLO('yolo11n.pt')
                _light_models[key] = m
            except Exception:
                return None
        return m
