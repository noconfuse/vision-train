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

def _safe_size(path):
    try:
        return os.path.getsize(path)
    except Exception:
        return 0

def _dir_size(root_dir, exts=None):
    total = 0
    try:
        for r, _, fs in os.walk(root_dir):
            for f in fs:
                if exts and not any(f.lower().endswith(e) for e in exts):
                    continue
                total += _safe_size(os.path.join(r, f))
    except Exception:
        return 0
    return total

def _pick_openvino_xml(path):
    if not path:
        return None
    if os.path.isfile(path) and path.lower().endswith('.xml'):
        return os.path.abspath(path)
    if os.path.isdir(path):
        cand = os.path.join(path, 'best.xml')
        if os.path.exists(cand):
            return os.path.abspath(cand)
        xmls = []
        for r, _, fs in os.walk(path):
            for f in fs:
                if f.lower().endswith('.xml'):
                    xmls.append(os.path.abspath(os.path.join(r, f)))
        if not xmls:
            return None
        xmls.sort(key=lambda p: (0 if os.path.basename(p) == 'best.xml' else 1, len(p), p))
        return xmls[0]
    return None

def _format_openvino_name(xml_path):
    try:
        base_dir = os.path.dirname(xml_path)
        meta = os.path.join(base_dir, 'metadata.yaml')
        if os.path.exists(meta):
            with open(meta, 'r', encoding='utf-8') as f:
                y = yaml.safe_load(f) or {}
            args = y.get('args') or {}
            if isinstance(args, dict) and args.get('int8') is True:
                return f"{os.path.basename(base_dir)} (OpenVINO INT8)"
        return f"{os.path.basename(base_dir)} (OpenVINO)"
    except Exception:
        return f"{os.path.basename(os.path.dirname(xml_path))} (OpenVINO)"

class ModelManager:
    """模型管理器"""
    
    @staticmethod
    def get_global_pretrained_models():
        """获取全局预训练模型"""
        models = []
        config_file = os.path.join(PRETRAINED_MODELS_DIR, "config.yaml")
        existing_paths = set()
        
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
                                ov_xml = _pick_openvino_xml(path)
                                add_path = ov_xml or (os.path.abspath(path) if os.path.exists(path) else None)
                                if add_path and add_path not in existing_paths and os.path.exists(add_path):
                                    if ov_xml:
                                        size = _dir_size(os.path.dirname(ov_xml), exts={'.xml', '.bin'})
                                        display_name = _format_openvino_name(ov_xml)
                                    else:
                                        size = _safe_size(add_path) if os.path.isfile(add_path) else _dir_size(add_path)
                                        display_name = name
                                    models.append({
                                        "name": display_name,
                                        "type": "pretrained",
                                        "path": os.path.abspath(add_path),
                                        "size": size,
                                        "is_global": True
                                    })
                                    existing_paths.add(os.path.abspath(add_path))
            except Exception as e:
                print(f"Error loading pretrained models config: {e}")

        # 2. 扫描 pretrained_models 目录下的模型文件/目录
        if os.path.exists(PRETRAINED_MODELS_DIR):
            for entry in os.listdir(PRETRAINED_MODELS_DIR):
                ep = os.path.join(PRETRAINED_MODELS_DIR, entry)
                add_path = None
                display_name = entry
                size = 0

                if os.path.isfile(ep) and entry.lower().endswith(('.pt', '.onnx', '.xml')):
                    add_path = os.path.abspath(ep)
                    size = _safe_size(add_path)
                    if entry.lower().endswith('.xml'):
                        display_name = _format_openvino_name(add_path)
                        size = _dir_size(os.path.dirname(add_path), exts={'.xml', '.bin'})
                elif os.path.isdir(ep):
                    ov_xml = _pick_openvino_xml(ep)
                    if ov_xml:
                        add_path = ov_xml
                        display_name = _format_openvino_name(ov_xml)
                        size = _dir_size(os.path.dirname(ov_xml), exts={'.xml', '.bin'})

                if add_path and add_path not in existing_paths and os.path.exists(add_path):
                    models.append({
                        "name": display_name,
                        "type": "pretrained",
                        "path": os.path.abspath(add_path),
                        "size": size,
                        "is_global": True
                    })
                    existing_paths.add(os.path.abspath(add_path))
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
                ip = os.path.join(models_dir, item)
                add_path = None
                display_name = item
                size = 0
                if os.path.isfile(ip) and item.lower().endswith(('.pt', '.onnx', '.xml')):
                    add_path = ip
                    size = _safe_size(add_path)
                    if item.lower().endswith('.xml'):
                        display_name = _format_openvino_name(add_path)
                        size = _dir_size(os.path.dirname(add_path), exts={'.xml', '.bin'})
                elif os.path.isdir(ip):
                    ov_xml = _pick_openvino_xml(ip)
                    if ov_xml:
                        add_path = ov_xml
                        display_name = _format_openvino_name(ov_xml)
                        size = _dir_size(os.path.dirname(ov_xml), exts={'.xml', '.bin'})
                if add_path and os.path.exists(add_path):
                    models.append({
                        "name": display_name,
                        "type": "pretrained",
                        "path": os.path.abspath(add_path),
                        "size": size
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
