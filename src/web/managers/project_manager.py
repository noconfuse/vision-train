import os
import json
import yaml
import shutil
from datetime import datetime
import sys

# Ensure parent directory is in sys.path for utils import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import PROJECT_ROOT

class ProjectManager:
    """项目管理器"""
    @staticmethod
    def scan_projects():
        """扫描所有可用项目"""
        projects = []
        projects_dir = os.path.join(PROJECT_ROOT, "projects")
        if not os.path.exists(projects_dir):
            return projects
        for item in os.listdir(projects_dir):
            project_path = os.path.join(projects_dir, item)
            if os.path.isdir(project_path):
                project_info = ProjectManager.load_project_info(project_path)
                if project_info:
                    projects.append(project_info)
        return sorted(projects, key=lambda x: x['name'])

    @staticmethod
    def load_project_info(project_path):
        """加载单个项目信息"""
        try:
            config_path = os.path.join(project_path, "project_config.json")
            if not os.path.exists(config_path):
                # 尝试从目录名恢复
                return {
                    "id": os.path.basename(project_path),
                    "name": os.path.basename(project_path),
                    "path": project_path,
                    "created_at": datetime.fromtimestamp(os.path.getctime(project_path)).strftime('%Y-%m-%d %H:%M:%S'),
                    "datasets": ProjectManager.scan_datasets(project_path)
                }
            with open(config_path, 'r', encoding='utf-8') as f:
                info = json.load(f)
                info['id'] = os.path.basename(project_path)
                info['path'] = project_path
                info['datasets'] = ProjectManager.scan_datasets(project_path)
                return info
        except Exception:
            return None

    @staticmethod
    def create_project(name, description=""):
        """创建新项目"""
        project_id = name # 简单使用名称作为ID
        projects_dir = os.path.join(PROJECT_ROOT, "projects")
        project_path = os.path.join(projects_dir, project_id)
        
        if os.path.exists(project_path):
            raise ValueError(f"项目 {name} 已存在")
            
        os.makedirs(project_path)
        os.makedirs(os.path.join(project_path, "datasets"))
        os.makedirs(os.path.join(project_path, "models"))
        os.makedirs(os.path.join(project_path, "training"))
        os.makedirs(os.path.join(project_path, "training_outputs"))
        
        info = {
            "name": name,
            "description": description,
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open(os.path.join(project_path, "project_config.json"), 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=2, ensure_ascii=False)
            
        return info

    @staticmethod
    def scan_datasets(project_path):
        """扫描项目下的数据集，返回前端需要的 {trainable: [], annotatable: []} 结构"""
        datasets = {
            'trainable': [],
            'annotatable': []
        }
        
        # 1. 扫描 datasets 目录（原始数据集） -> annotatable
        raw_dir = os.path.join(project_path, "datasets")
        if os.path.exists(raw_dir):
            for item in os.listdir(raw_dir):
                p = os.path.join(raw_dir, item)
                if os.path.isdir(p):
                    analysis = ProjectManager.analyze_dataset(p)
                    info = {
                        "name": item,
                        "type": "raw",
                        "path": p,
                        "image_count": analysis['image_count'],
                        "label_count": analysis['label_count'],
                        "annotation_rate": analysis['annotation_rate'],
                        "classes": analysis['classes']
                    }
                    datasets['annotatable'].append(info)
                    
        # 2. 扫描 training 目录（训练用数据集） -> trainable & annotatable
        train_dir = os.path.join(project_path, "training")
        if os.path.exists(train_dir):
            for item in os.listdir(train_dir):
                p = os.path.join(train_dir, item)
                if os.path.isdir(p):
                    # 详细分析
                    analysis = ProjectManager.analyze_dataset(p)
                    
                    info = {
                        "name": item,
                        "type": "training",
                        "path": p,
                        "image_count": analysis['image_count'],
                        "label_count": analysis['label_count'],
                        "annotation_rate": analysis['annotation_rate'],
                        "classes": analysis['classes']
                    }
                    
                    # 检查是否符合 YOLO 训练要求
                    data_yaml_exists = os.path.exists(os.path.join(p, 'data.yaml')) or \
                                     os.path.exists(os.path.join(p, 'dataset.yaml'))
                    
                    is_yolo = data_yaml_exists or \
                             (os.path.exists(os.path.join(p, 'train')) and os.path.exists(os.path.join(p, 'val')))
                    
                    if is_yolo:
                        datasets['trainable'].append(info)
                    else:
                        datasets['annotatable'].append(info)
                        
        return datasets

    @staticmethod
    def count_images(path):
        """统计图片数量"""
        count = 0
        for root, _, files in os.walk(path):
            for f in files:
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    count += 1
        return count

    @staticmethod
    def analyze_dataset(dataset_path):
        """分析数据集详细信息"""
        info = {
            "image_count": 0,
            "label_count": 0, # 标注文件数
            "total_objects": 0, # 总目标框数
            "classes": [], # 兼容旧字段
            "class_stats": [], # 前端需要的详细统计
            "names": [], # 类别名称列表，供 ImageAnnotator 使用
            "has_train": False,
            "has_val": False,
            "has_test": False,
            "annotation_rate": 0.0,
            "tags": []
        }
        
        class_counts = {} # {class_id: count}
        
        # 尝试读取 data.yaml 获取类别名称
        class_names = {}
        data_yaml_path = os.path.join(dataset_path, 'data.yaml')
        if not os.path.exists(data_yaml_path):
            data_yaml_path = os.path.join(dataset_path, 'dataset.yaml')
            
        if os.path.exists(data_yaml_path):
            try:
                with open(data_yaml_path, 'r') as f:
                    data_config = yaml.safe_load(f)
                    if 'names' in data_config:
                        names = data_config['names']
                        if isinstance(names, list):
                            for i, name in enumerate(names):
                                class_names[i] = name
                        elif isinstance(names, dict):
                            for k, v in names.items():
                                class_names[int(k)] = v
                    if 'tags' in data_config:
                        t = data_config['tags']
                        if isinstance(t, list):
                            info['tags'] = t
            except:
                pass
        
        # 填充 names 列表
        max_id = max(class_names.keys()) if class_names else -1
        for i in range(max_id + 1):
            info['names'].append(class_names.get(i, f"class_{i}"))

        # 检查目录结构
        splits = ['train', 'val', 'test']
        
        def scan_split(img_dir, lbl_dir):
            if not os.path.exists(img_dir):
                return False
                
            # 统计图片
            imgs = [f for f in os.listdir(img_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            if not imgs:
                return False
                
            info['image_count'] += len(imgs)
            
            # 统计标注
            if os.path.exists(lbl_dir):
                lbls = [f for f in os.listdir(lbl_dir) if f.lower().endswith('.txt')]
                info['label_count'] += len(lbls)
                
                # 分析类别
                for l in lbls:
                    try:
                        with open(os.path.join(lbl_dir, l), 'r') as f:
                            for line in f:
                                parts = line.strip().split()
                                if parts:
                                    cls_id = int(float(parts[0]))
                                    class_counts[cls_id] = class_counts.get(cls_id, 0) + 1
                                    info['total_objects'] += 1
                    except:
                        pass
            return True

        has_split = False
        for split in splits:
            img_dir = os.path.join(dataset_path, split, 'images')
            lbl_dir = os.path.join(dataset_path, split, 'labels')
            if scan_split(img_dir, lbl_dir):
                info[f'has_{split}'] = True
                has_split = True
        
        # 如果没有 split 结构，尝试根目录
        if not has_split:
            scan_split(os.path.join(dataset_path, 'images'), os.path.join(dataset_path, 'labels'))
            
        if info['image_count'] > 0:
            info['annotation_rate'] = info['label_count'] / info['image_count']
        
        # 格式化类别信息
        for cls_id in sorted(class_counts.keys()):
            count = class_counts[cls_id]
            percentage = round((count / info['total_objects'] * 100), 1) if info['total_objects'] > 0 else 0
            stats = {
                "id": cls_id,
                "name": class_names.get(cls_id, f"class_{cls_id}"),
                "count": count,
                "percentage": percentage
            }
            info['classes'].append(stats)
            info['class_stats'].append(stats)
            
        return info
