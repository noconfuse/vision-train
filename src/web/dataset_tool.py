#!/usr/bin/env python3
"""
数据集工具 - 以训练为主、标注为辅的深度学习数据集管理平台
"""

import os
import json
import glob
import time
import yaml
import threading
import sys
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from PIL import Image
import subprocess
import csv
import urllib.request
import shutil
import re

# 项目配置
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
PRETRAINED_MODELS_DIR = os.path.join(PROJECT_ROOT, "pretrained_models")

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.secret_key = 'dataset_tool_secret_key'

# 全局状态
current_project = None
training_status = {
    'is_running': False,
    'progress': 0,
    'message': '',
    'start_time': None,
    'results': {}
}

export_status = {
    'is_running': False,
    'progress': 0,
    'message': '',
    'start_time': None,
    'results': {},
    'export_id': None
}

eval_status = {
    'is_running': False,
    'progress': 0,
    'message': '',
    'start_time': None,
    'results': {}
}

def get_device():
    try:
        import torch
        return '0' if torch.cuda.is_available() else 'cpu'
    except Exception:
        return 'cpu'

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
        """加载项目信息"""
        project_name = os.path.basename(project_path)
        
        # 统计数据集信息
        datasets = ProjectManager.scan_datasets(project_path)
        
        return {
            'id': project_name,
            'name': project_name,
            'path': project_path,
            'datasets': datasets,
            'created_time': os.path.getctime(project_path)
        }
    
    @staticmethod
    def scan_datasets(project_path):
        datasets = {
            'trainable': [],
            'annotatable': []
        }
        training_root = os.path.join(project_path, "training")
        if os.path.isdir(training_root):
            for entry in sorted(os.listdir(training_root)):
                if not entry.startswith("datasets"):
                    continue
                ds_path = os.path.join(training_root, entry)
                if os.path.isdir(ds_path):
                    info = ProjectManager.analyze_training_structure(ds_path)
                    if info:
                        datasets['trainable'].append(info)
        return datasets
    
    @staticmethod
    def analyze_training_structure(training_path):
        """分析数据集目录（固定为 {split}/images 与 {split}/labels 结构）"""
        dataset_name = os.path.basename(training_path)
        
        # 统计所有图片和标签
        total_images = 0
        total_labels = 0
        has_train = False
        has_val = False
        has_test = False
        
        def collect(split):
            img_dir = os.path.join(training_path, split, "images")
            lbl_dir = os.path.join(training_path, split, "labels")
            if not os.path.exists(img_dir):
                return 0, 0, False
            images = []
            for root, _, fs in os.walk(img_dir):
                for f in fs:
                    if f.lower().endswith((".jpg", ".jpeg", ".png")):
                        images.append(os.path.join(root, f))
            labeled = 0
            if os.path.exists(lbl_dir):
                for img in images:
                    rel = os.path.relpath(img, img_dir)
                    lbl_path = os.path.join(lbl_dir, os.path.splitext(rel)[0] + ".txt")
                    if os.path.exists(lbl_path):
                        labeled += 1
            return len(images), labeled, True

        labeled_images = 0
        n_imgs, n_lbls, ok = collect("train")
        if ok:
            has_train = True
            total_images += n_imgs
            labeled_images += n_lbls
        n_imgs, n_lbls, ok = collect("val")
        if ok:
            has_val = True
            total_images += n_imgs
            labeled_images += n_lbls
        n_imgs, n_lbls, ok = collect("test")
        if ok:
            has_test = True
            total_images += n_imgs
            labeled_images += n_lbls
        total_labels = labeled_images
        
        # 如果没有找到任何图片，返回None
        if total_images == 0:
            return None
        
        # 检查配置文件
        config_files = []
        for file in os.listdir(training_path):
            if file.endswith(('.yaml', '.yml')):
                config_files.append(file)
        
        return {
            'name': dataset_name,
            'path': training_path,
            'image_count': total_images,
            'label_count': total_labels,
            'annotation_rate': (total_labels / total_images) if total_images > 0 else 0,
            'needs_annotation': total_labels < total_images,
            'has_train': has_train,
            'has_val': has_val,
            'has_test': has_test,
            'config_files': config_files,
            'last_modified': os.path.getmtime(training_path)
        }
    
    @staticmethod
    def analyze_dataset(dataset_path):
        """分析数据集信息（固定为 {split}/images 与 {split}/labels 结构）"""
        dataset_name = os.path.basename(dataset_path)
        
        def count_split(split):
            imgs = 0
            lbls = 0
            img_dir = os.path.join(dataset_path, split, "images")
            lbl_dir = os.path.join(dataset_path, split, "labels")
            if not os.path.exists(img_dir):
                return 0, 0, False
            for root, _, fs in os.walk(img_dir):
                for f in fs:
                    if f.lower().endswith((".jpg", ".jpeg", ".png")):
                        imgs += 1
            if os.path.exists(lbl_dir):
                for root, _, fs in os.walk(lbl_dir):
                    for f in fs:
                        if f.lower().endswith(".txt"):
                            lbls += 1
            return imgs, lbls, True

        image_count = 0
        label_count = 0
        has_train = False
        has_val = False
        has_test = False
        for sp in ("train", "val", "test"):
            imgs, lbls, ok = count_split(sp)
            if ok:
                image_count += imgs
                label_count += lbls
                if sp == "train":
                    has_train = True
                elif sp == "val":
                    has_val = True
                elif sp == "test":
                    has_test = True
        if image_count == 0:
            return None
        
        # 检查配置文件
        config_files = []
        for file in os.listdir(dataset_path):
            if file.endswith(('.yaml', '.yml')):
                config_files.append(file)
        
        return {
            'name': dataset_name,
            'path': dataset_path,
            'image_count': image_count,
            'label_count': label_count,
            'annotation_rate': label_count / image_count if image_count > 0 else 0,
            'needs_annotation': label_count < image_count,
            'has_train': has_train,
            'has_val': has_val,
            'has_test': has_test,
            'config_files': config_files,
            'last_modified': os.path.getmtime(dataset_path)
        }

class ModelManager:
    """预训练模型管理器"""
    
    @staticmethod
    def get_pretrained_models():
        items = {}
        config_file = os.path.join(PRETRAINED_MODELS_DIR, "config.yaml")
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
                confs = cfg.get('pretrained_models') or {}
                if isinstance(confs, dict):
                    for key, item in confs.items():
                        name = item.get('name') or key
                        path = item.get('path')
                        url = item.get('url')
                        if path and not os.path.isabs(path):
                            path = os.path.join(PROJECT_ROOT, path)
                        if path:
                            items[os.path.abspath(path)] = {
                                'name': name,
                                'path': os.path.abspath(path),
                                'url': url,
                                'description': item.get('description', '预训练模型'),
                                'size': item.get('size')
                            }
        def _size(p):
            try:
                if os.path.isdir(p):
                    total = 0
                    for r, _, fs in os.walk(p):
                        for f in fs:
                            total += os.path.getsize(os.path.join(r, f))
                    return total
                return os.path.getsize(p)
            except Exception:
                return None
        if os.path.exists(PRETRAINED_MODELS_DIR):
            for entry in os.listdir(PRETRAINED_MODELS_DIR):
                ep = os.path.join(PRETRAINED_MODELS_DIR, entry)
                add_path = None
                if os.path.isfile(ep) and entry.lower().endswith(('.pt', '.onnx', '.xml')):
                    add_path = os.path.abspath(ep)
                elif os.path.isdir(ep):
                    xmls = []
                    for r, _, fs in os.walk(ep):
                        for f in fs:
                            if f.lower().endswith('.xml'):
                                xmls.append(os.path.abspath(os.path.join(r, f)))
                    if xmls:
                        add_path = xmls[0]
                if add_path and add_path not in items:
                    items[add_path] = {
                        'name': os.path.splitext(os.path.basename(add_path))[0],
                        'path': add_path,
                        'url': '',
                        'description': '预训练模型',
                        'size': _size(add_path)
                    }
        # 扫描项目训练产物（training_outputs/*/*/weights/best.pt）并加入可选模型
        projects_dir = os.path.join(PROJECT_ROOT, 'projects')
        for proj in os.listdir(projects_dir) if os.path.exists(projects_dir) else []:
            pdir = os.path.join(projects_dir, proj, 'training_outputs')
            if not os.path.exists(pdir):
                continue
            for ds in os.listdir(pdir):
                ds_dir = os.path.join(pdir, ds)
                if not os.path.isdir(ds_dir):
                    continue
                for rid in os.listdir(ds_dir):
                    for sub in ('run','stage1','stage2'):
                        wbest = os.path.join(ds_dir, rid, sub, 'weights', 'best.pt')
                        if os.path.exists(wbest):
                            k = os.path.abspath(wbest)
                            if k not in items:
                                items[k] = {
                                    'name': f"{proj}/{ds}/{rid}/best.pt",
                                    'path': k,
                                    'url': '',
                                    'description': '项目训练产物',
                                    'size': _size(k)
                                }
        models = list(items.values())
        return models


    @staticmethod
    def ensure_local_model(model):
        """确保模型权重存在本地；若缺失则下载或从Ultralytics缓存复制到pretrained_models目录"""
        path = model.get('path')
        url = model.get('url')
        name = (model.get('name') or '').lower()
        # 规范化目标路径
        if path and not os.path.isabs(path):
            path = os.path.join(PROJECT_ROOT, path)
        # 推断文件名
        filename = None
        if path:
            filename = os.path.basename(path)
        elif name:
            filename = f"{name}.pt" if not name.endswith('.pt') else name
            path = os.path.join(PRETRAINED_MODELS_DIR, filename)
        else:
            raise FileNotFoundError('模型未提供有效的path或name')
        # 已存在直接返回
        if os.path.exists(path):
            return path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # 尝试显式URL下载
        if not url:
            base_names = {"yolo11n","yolo11s","yolo11m","yolo11l","yolo11x"}
            if name in base_names or (filename and filename.replace('.pt','') in base_names):
                fn = filename or f"{name}.pt"
                url = f"https://github.com/ultralytics/assets/releases/download/v8.3.0/{fn}"
        if url:
            try:
                urllib.request.urlretrieve(url, path)
                if os.path.exists(path):
                    return path
            except Exception:
                pass
        # 使用Ultralytics触发下载到缓存
        try:
            from ultralytics import YOLO
            YOLO(filename or name)  # 触发下载
        except Exception:
            pass
        # 在常见缓存位置搜索并复制
        candidate_dirs = [
            os.path.expanduser('~/.cache/ultralytics/weights'),
            os.path.expanduser('~/.cache/Ultralytics/weights'),
            os.path.expanduser('~/.cache/ultralytics'),
            os.path.expanduser('~/.cache/Ultralytics'),
        ]
        for d in candidate_dirs:
            src = os.path.join(d, filename)
            if os.path.exists(src):
                shutil.copy2(src, path)
                return path
        # 兜底全局搜索
        for d in candidate_dirs:
            for root, _, files in os.walk(d):
                if filename in files:
                    src = os.path.join(root, filename)
                    shutil.copy2(src, path)
                    return path
        # 进一步回退：检查当前工作目录或PROJECT_ROOT是否已存在下载的文件
        local_candidates = [
            os.path.join(os.getcwd(), filename),
            os.path.join(PROJECT_ROOT, filename)
        ]
        for src in local_candidates:
            if os.path.exists(src):
                shutil.copy2(src, path)
                return path
        raise FileNotFoundError(f"无法获取模型文件: {path}")
    
    @staticmethod
    def get_model_config(model_name):
        """获取指定模型的配置信息；支持直接传绝对路径作为模型名"""
        # 若 model_name 是文件路径，则直接返回
        if model_name and (os.path.isabs(model_name) or model_name.endswith('.pt')) and os.path.exists(model_name):
            return {'name': os.path.basename(model_name), 'path': os.path.abspath(model_name), 'url': ''}
        models = ModelManager.get_pretrained_models()
        for model in models:
            if model.get('name') == model_name:
                return model
        # 如果未找到，尝试在本地按名称匹配文件
        cand = os.path.join(PRETRAINED_MODELS_DIR, f"{model_name}.pt")
        if os.path.exists(cand):
            return {'name': model_name, 'path': os.path.abspath(cand), 'url': ''}
        return None
# 轻量模型缓存
_light_models = {}

def _get_auto_annotate_model(project_path=None, prefer_project_best=True):
    try:
        from ultralytics import YOLO
    except Exception:
        return None
    # 优先使用项目最新训练权重
    if prefer_project_best and project_path:
        arts = TrainingManager.get_latest_artifacts(project_path)
        w = arts.get('weights_best') or arts.get('weights_last')
        if w and os.path.exists(w):
            key = f"best:{w}"
            m = _light_models.get(key)
            if m is None:
                m = YOLO(w)
                _light_models[key] = m
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
    

class TrainingManager:
    """训练管理器"""
    
    @staticmethod
    def start_training(project_path, dataset_name, model_name, training_config=None, dataset_path=None):
        """开始训练任务"""
        global training_status
        
        try:
            # 验证输入参数
            if not project_path or not dataset_name or not model_name:
                return {'success': False, 'error': '缺少必要的训练参数'}
            
            model_config = ModelManager.get_model_config(model_name)
            if not model_config:
                return {'success': False, 'error': f'找不到模型配置: {model_name}'}
            model_path = model_config.get('path')

            dataset_dir = dataset_path or os.path.join(project_path, dataset_name)
            dataset_yaml = None
            for y in (
                os.path.join(dataset_dir, 'dataset.yaml'),
                os.path.join(dataset_dir, 'data.yaml')
            ):
                if os.path.exists(y):
                    dataset_yaml = y
                    break
            if not dataset_yaml:
                for f in os.listdir(dataset_dir):
                    if f.endswith(('.yaml', '.yml')):
                        p = os.path.join(dataset_dir, f)
                        dataset_yaml = p
                        break
            if not dataset_yaml:
                return {'success': False, 'error': '未找到数据集配置文件'}
            try:
                with open(dataset_yaml, 'r', encoding='utf-8') as f:
                    y = yaml.safe_load(f) or {}
                p = y.get('path')
                if not p or not os.path.exists(p):
                    y['path'] = dataset_dir
                    with open(dataset_yaml, 'w', encoding='utf-8') as f:
                        yaml.safe_dump(y, f, allow_unicode=True)
                # 校验与修正 split 路径（val/test 为空时回退到 train）
                def _resolve(x):
                    if not x:
                        return None
                    return x if os.path.isabs(x) else os.path.join(y.get('path') or dataset_dir, x)
                def _img_count(d):
                    if not d or not os.path.exists(d):
                        return 0
                    c = 0
                    for r, _, fs in os.walk(d):
                        for f in fs:
                            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                                c += 1
                    return c
                train_dir = _resolve(y.get('train') or 'images/train')
                val_dir = _resolve(y.get('val'))
                test_dir = _resolve(y.get('test'))
                # 如果 val 未配置或为空，则回退到 train 以保证训练正常
                if _img_count(val_dir) == 0 and _img_count(train_dir) > 0:
                    y['val'] = 'images/train'
                # 如果 test 未配置或为空，允许为空，YOLO 会跳过；无需强制设置
                with open(dataset_yaml, 'w', encoding='utf-8') as f:
                    yaml.safe_dump(y, f, allow_unicode=True)
            except Exception:
                pass
            
            # 创建训练输出目录（包含数据集名）
            training_output_dir = os.path.join(project_path, "training_outputs", dataset_name)
            os.makedirs(training_output_dir, exist_ok=True)
            
            # 生成训练ID
            training_id = f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            training_dir = os.path.join(training_output_dir, training_id)
            os.makedirs(training_dir, exist_ok=True)
            
            # 更新训练状态
            training_status.update({
                'is_running': True,
                'progress': 0,
                'message': '准备训练环境...',
                'start_time': datetime.now().isoformat(),
                'training_id': training_id,
                'project_path': project_path,
                'dataset_name': dataset_name,
                'model_name': model_name,
                'results': {}
            })
            
            config_file = os.path.join(training_dir, "training_config.json")
            training_info = {
                'training_id': training_id,
                'project_path': project_path,
                'dataset_name': dataset_name,
                'model_name': model_name,
                'model_path': model_path,
                'model_url': model_config.get('url'),
                'dataset_yaml': dataset_yaml,
                'model_config': model_config,
                'training_config': training_config or {},
                'start_time': training_status['start_time'],
                'status': 'running'
            }
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(training_info, f, ensure_ascii=False, indent=2)
            
            import threading
            training_thread = threading.Thread(
                target=TrainingManager._run_yolo_training,
                args=(training_dir, training_info)
            )
            training_thread.start()
            
            return {
                'success': True,
                'training_id': training_id,
                'message': '训练任务已启动'
            }
            
        except Exception as e:
            training_status['is_running'] = False
            training_status['message'] = f'训练启动失败: {str(e)}'
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _run_yolo_training(training_dir, training_info):
        global training_status
        
        try:
            training_status['message'] = '下载预训练模型...'
            try:
                ensured_path = ModelManager.ensure_local_model({
                    'name': training_info['model_name'],
                    'path': training_info.get('model_path'),
                    'url': training_info.get('model_url')
                })
                training_info['model_path'] = ensured_path
            except Exception as e:
                training_status['message'] = f'模型下载失败: {str(e)}'
                training_status['is_running'] = False
                return
            training_status['message'] = '启动训练'
            device = get_device()
            cpu_mode = str(device).lower() == 'cpu'
            yolo_bin = os.path.join(os.environ.get('VIRTUAL_ENV') or os.path.dirname(sys.executable), 'bin', 'yolo')
            if not os.path.exists(yolo_bin):
                yolo_bin = os.path.join(PROJECT_ROOT, 'myenv', 'bin', 'yolo')
            # 统一使用单一目录名 'run'，并清理可能存在的遗留目录
            try:
                run_path = os.path.join(training_dir, 'run')
                if os.path.exists(run_path):
                    # 保留目录但清空其内容，避免 Ultralytics 生成 run2
                    for root, dirs, files in os.walk(run_path):
                        for f in files:
                            try:
                                os.remove(os.path.join(root, f))
                            except Exception:
                                pass
                        for d in dirs:
                            try:
                                shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                            except Exception:
                                pass
                else:
                    os.makedirs(run_path, exist_ok=True)
            except Exception:
                pass
            cmd = [
                yolo_bin,
                'train',
                f"data={training_info['dataset_yaml']}",
                f"model={training_info['model_path']}",
                f"project={training_dir}",
                'name=run',
                'save=True',
                'plots=True',
                'exist_ok=True',
                'amp=False',
                f"device={device}"
            ]
            tc = training_info.get('training_config') or {}
            def _add_arg(name):
                v = tc.get(name)
                if v is None or v == '':
                    return
                cmd.append(f"{name}={v}")
            _add_arg('epochs')
            if cpu_mode:
                cmd.append('batch=1')
            else:
                _add_arg('batch')
            _add_arg('freeze')
            # imgsz 仅在有效时追加（int或list）；None/空字符串不追加，使用默认
            v_img = tc.get('imgsz')
            if v_img is not None and v_img != '':
                cmd.append(f"imgsz={v_img}")
            _add_arg('lr0')
            if cpu_mode:
                cmd.append('workers=0')
            start_time = time.time()
            last_line = ''
            p = None
            save_dir = None
            try:
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in p.stdout:
                    if not training_status['is_running']:
                        try:
                            p.terminate()
                        except Exception:
                            pass
                        break
                    last_line = line.strip()
                    training_status['message'] = last_line[:200]
                    try:
                        m = re.search(r'(\b|^)(\d+)\s*/\s*(\d+)(\b|$)', last_line)
                        if m:
                            cur = int(m.group(2)); tot = int(m.group(3));
                            if tot > 0:
                                training_status['progress'] = max(training_status['progress'], min(100, int(cur * 100 / tot)))
                        m2 = re.search(r"save_dir\s*=\s*(.+)$", last_line)
                        if not m2:
                            m2 = re.search(r"Results saved to\s*(.+)$", last_line)
                        if m2:
                            s = m2.group(1).strip()
                            if s:
                                save_dir = s
                    except Exception:
                        pass
                p.wait()
            except FileNotFoundError:
                from ultralytics import YOLO
                model = YOLO(training_info['model_path'])
                kwargs = {
                    'data': training_info['dataset_yaml'],
                    'project': training_dir,
                    'name': 'run',
                    'save': True,
                    'plots': True,
                    'device': device,
                    'amp': False,
                }
                if cpu_mode:
                    kwargs['batch'] = 1
                    kwargs['workers'] = 0
                if tc.get('epochs') not in (None, ''):
                    kwargs['epochs'] = tc.get('epochs')
                if (not cpu_mode) and tc.get('batch') not in (None, ''):
                    kwargs['batch'] = tc.get('batch')
                if tc.get('freeze') not in (None, ''):
                    kwargs['freeze'] = tc.get('freeze')
                if tc.get('imgsz') not in (None, ''):
                    kwargs['imgsz'] = tc.get('imgsz')
                if tc.get('lr0') not in (None, ''):
                    kwargs['lr0'] = tc.get('lr0')
                model.train(**kwargs)
            run_dir = os.path.join(training_dir, 'run')
            if not os.path.exists(run_dir):
                os.makedirs(run_dir, exist_ok=True)
            weights_best = os.path.join(run_dir, 'weights', 'best.pt')
            results_csv = os.path.join(run_dir, 'results.csv')
            results_png = os.path.join(run_dir, 'results.png')
            if (p and p.returncode and p.returncode != 0):
                try:
                    from ultralytics import YOLO
                    # 若amp自检加载内置yolo11n.pt失败，先确保本地存在可用的yolo11n.pt
                    try:
                        nn_local = os.path.join(PROJECT_ROOT, 'yolo11n.pt')
                        if not os.path.exists(nn_local):
                            open(nn_local, 'wb').close()
                        os.environ.setdefault('ULTRALYTICS_CACHE_DIR', os.path.join(os.path.expanduser('~'), '.cache', 'ultralytics'))
                    except Exception:
                        pass
                    model = YOLO(training_info['model_path'])
                    kwargs = {
                        'data': training_info['dataset_yaml'],
                        'project': training_dir,
                        'name': 'run',
                        'save': True,
                        'plots': True,
                        'device': device,
                        'amp': False,
                    }
                    cpu_mode2 = str(device).lower() == 'cpu'
                    if cpu_mode2:
                        kwargs['batch'] = 1
                        kwargs['workers'] = 0
                    if tc.get('epochs') not in (None, ''):
                        kwargs['epochs'] = tc.get('epochs')
                    if (not cpu_mode2) and tc.get('batch') not in (None, ''):
                        kwargs['batch'] = tc.get('batch')
                    if tc.get('freeze') not in (None, ''):
                        kwargs['freeze'] = tc.get('freeze')
                    if tc.get('imgsz') not in (None, ''):
                        kwargs['imgsz'] = tc.get('imgsz')
                    if tc.get('lr0') not in (None, ''):
                        kwargs['lr0'] = tc.get('lr0')
                    model.train(**kwargs)
                except Exception as e:
                    training_status['message'] = f'训练失败: {str(e)} 或 CLI: {last_line[:120]}'
                    training_status['is_running'] = False
                    return
            weights_last = os.path.join(run_dir, 'weights', 'last.pt')
            metrics = {}
            if os.path.exists(results_csv):
                try:
                    with open(results_csv, 'r') as f:
                        rows = list(csv.DictReader(f))
                        if rows:
                            metrics = rows[-1]
                except Exception:
                    pass
            def _sz(p):
                try:
                    return os.path.getsize(p) if p and os.path.exists(p) else 0
                except Exception:
                    return 0
            results = {
                'best_model_path': weights_best if os.path.exists(weights_best) else (weights_last if os.path.exists(weights_last) else ''),
                'last_model_path': weights_last if os.path.exists(weights_last) else '',
                'best_size_bytes': _sz(weights_best),
                'last_size_bytes': _sz(weights_last),
                'results_csv': results_csv if os.path.exists(results_csv) else '',
                'results_png': results_png if os.path.exists(results_png) else '',
                'metrics': metrics,
                'training_dir': run_dir,
                'training_time': int(time.time() - start_time)
            }
            training_status['results'] = results
            training_status['message'] = '训练完成'
            training_status['progress'] = 100
            training_status['is_running'] = False
            training_info['status'] = 'completed'
            training_info['end_time'] = datetime.now().isoformat()
            training_info['results'] = results
            cfg_file = os.path.join(training_dir, 'training_config.json')
            with open(cfg_file, 'w', encoding='utf-8') as f:
                json.dump(training_info, f, ensure_ascii=False, indent=2)
        
        except Exception as e:
            training_status['message'] = f'训练失败: {str(e)}'
            training_status['is_running'] = False

    @staticmethod
    def start_two_stage_training(project_path, dataset_name, model_name, stage1_config=None, stage2_config=None, dataset_path=None, stage2_dataset_path=None):
        global training_status
        try:
            if not project_path or not dataset_name or not model_name:
                return {'success': False, 'error': '缺少必要参数'}
            model_config = ModelManager.get_pretrained_models()
            mdl = None
            for m in model_config:
                if m.get('name') == model_name:
                    mdl = m
                    break
            if not mdl:
                return {'success': False, 'error': f'找不到模型配置: {model_name}'}
            model_path = mdl.get('path')
            dataset_dir = dataset_path or os.path.join(project_path, dataset_name)
            dataset_yaml = None
            for y in (os.path.join(dataset_dir, 'dataset.yaml'), os.path.join(dataset_dir, 'data.yaml')):
                if os.path.exists(y):
                    dataset_yaml = y
                    break
            if not dataset_yaml:
                for f in os.listdir(dataset_dir):
                    if f.endswith(('.yaml', '.yml')):
                        dataset_yaml = os.path.join(dataset_dir, f)
                        break
            if not dataset_yaml:
                return {'success': False, 'error': '未找到数据集配置文件'}
            try:
                with open(dataset_yaml, 'r', encoding='utf-8') as f:
                    y = yaml.safe_load(f) or {}
                p = y.get('path')
                if not p or not os.path.exists(p):
                    y['path'] = dataset_dir
                def _resolve(x):
                    if not x:
                        return None
                    return x if os.path.isabs(x) else os.path.join(y.get('path') or dataset_dir, x)
                def _img_count(d):
                    if not d or not os.path.exists(d):
                        return 0
                    c = 0
                    for r, _, fs in os.walk(d):
                        for f in fs:
                            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                                c += 1
                    return c
                train_dir = _resolve(y.get('train') or 'images/train')
                val_dir = _resolve(y.get('val'))
                if _img_count(val_dir) == 0 and _img_count(train_dir) > 0:
                    y['val'] = 'images/train'
                with open(dataset_yaml, 'w', encoding='utf-8') as f:
                    yaml.safe_dump(y, f, allow_unicode=True)
            except Exception:
                pass
            training_output_dir = os.path.join(project_path, "training_outputs", dataset_name)
            os.makedirs(training_output_dir, exist_ok=True)
            training_id = f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}_2stage"
            training_dir = os.path.join(training_output_dir, training_id)
            os.makedirs(training_dir, exist_ok=True)
            training_status.update({'is_running': True, 'progress': 0, 'message': '准备两阶段训练...', 'start_time': datetime.now().isoformat(), 'training_id': training_id, 'project_path': project_path, 'dataset_name': dataset_name, 'model_name': model_name, 'results': {}})
            # resolve stage2 dataset yaml
            dataset_yaml_2 = None
            if stage2_dataset_path:
                try:
                    if not os.path.isabs(stage2_dataset_path):
                        stage2_dataset_path = os.path.join(PROJECT_ROOT, stage2_dataset_path)
                    for y in (os.path.join(stage2_dataset_path, 'dataset.yaml'), os.path.join(stage2_dataset_path, 'data.yaml')):
                        if os.path.exists(y):
                            dataset_yaml_2 = y
                            break
                    if not dataset_yaml_2:
                        for f in os.listdir(stage2_dataset_path):
                            if f.endswith(('.yaml','.yml')):
                                dataset_yaml_2 = os.path.join(stage2_dataset_path, f)
                                break
                except Exception:
                    dataset_yaml_2 = None
            if dataset_yaml_2:
                dataset_yaml_2 = os.path.abspath(dataset_yaml_2)
                try:
                    with open(dataset_yaml_2, 'r', encoding='utf-8') as f:
                        y2 = yaml.safe_load(f) or {}
                    p2 = y2.get('path')
                    if not p2 or not os.path.exists(p2):
                        y2['path'] = stage2_dataset_path
                    def _resolve2(x):
                        if not x:
                            return None
                        return x if os.path.isabs(x) else os.path.join(y2.get('path') or stage2_dataset_path, x)
                    def _img_count2(d):
                        if not d or not os.path.exists(d):
                            return 0
                        c = 0
                        for r, _, fs in os.walk(d):
                            for f in fs:
                                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                                    c += 1
                        return c
                    train2 = _resolve2(y2.get('train') or 'images/train')
                    val2 = _resolve2(y2.get('val'))
                    if _img_count2(val2) == 0 and _img_count2(train2) > 0:
                        y2['val'] = 'images/train'
                    with open(dataset_yaml_2, 'w', encoding='utf-8') as f:
                        yaml.safe_dump(y2, f, allow_unicode=True)
                except Exception:
                    pass
            info = {'training_id': training_id, 'project_path': project_path, 'dataset_name': dataset_name, 'model_name': model_name, 'model_path': model_path, 'dataset_yaml': dataset_yaml, 'stage2_dataset_yaml': dataset_yaml_2 or dataset_yaml, 'stage1': stage1_config or {}, 'stage2': stage2_config or {}, 'status': 'running'}
            cfg_file = os.path.join(training_dir, 'training_config.json')
            with open(cfg_file, 'w', encoding='utf-8') as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
            def _run_two_stage():
                try:
                    os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
                    ensured = ModelManager.ensure_local_model({'name': model_name, 'path': model_path, 'url': mdl.get('url')})
                    device = get_device()
                    from ultralytics import YOLO
                    model = YOLO(ensured)
                    s1 = info['stage1']
                    kwargs1 = {'data': dataset_yaml, 'project': training_dir, 'name': 'stage1', 'save': True, 'plots': True, 'device': device}
                    if str(device).lower() == 'cpu':
                        kwargs1['workers'] = 0
                        kwargs1['batch'] = 1
                    if s1.get('epochs') not in (None, ''): kwargs1['epochs'] = s1.get('epochs')
                    if str(device).lower() != 'cpu' and s1.get('batch') not in (None, ''): kwargs1['batch'] = s1.get('batch')
                    if s1.get('imgsz') not in (None, ''): kwargs1['imgsz'] = s1.get('imgsz')
                    if s1.get('lr0') not in (None, ''): kwargs1['lr0'] = s1.get('lr0')
                    if s1.get('freeze') not in (None, ''): kwargs1['freeze'] = s1.get('freeze')
                    training_status['message'] = '阶段一训练中...'
                    def _monitor(csv_path, total_epochs, start_p, span_p, stop_event, stage_text):
                        while not stop_event.is_set():
                            try:
                                if os.path.exists(csv_path):
                                    with open(csv_path, 'r') as f:
                                        rows = list(csv.DictReader(f))
                                    if rows:
                                        ep = rows[-1].get('epoch')
                                        try:
                                            cur = int(float(ep)) + 1
                                        except Exception:
                                            cur = len(rows)
                                        tot = int(total_epochs) if total_epochs else 100
                                        prog = start_p + span_p * max(0.0, min(1.0, cur / max(1, tot)))
                                        training_status['progress'] = int(round(prog))
                                        training_status['message'] = f'{stage_text} {cur}/{tot}'
                                time.sleep(1)
                            except Exception:
                                time.sleep(1)
                    csv1 = os.path.join(training_dir, 'stage1', 'results.csv')
                    e1 = threading.Event()
                    t1 = threading.Thread(target=_monitor, args=(csv1, kwargs1.get('epochs'), 0, 50, e1, '阶段一训练中...'))
                    t1.daemon = True
                    t1.start()
                    model.train(**kwargs1)
                    e1.set()
                    training_status['progress'] = max(training_status.get('progress', 0), 50)
                    s1_weights = os.path.join(training_dir, 'stage1', 'weights', 'best.pt')
                    if not os.path.exists(s1_weights):
                        s1_weights = os.path.join(training_dir, 'stage1', 'weights', 'last.pt')
                    model2 = YOLO(s1_weights)
                    s2 = info['stage2']
                    data2 = info.get('stage2_dataset_yaml') or dataset_yaml
                    kwargs2 = {'data': data2, 'project': training_dir, 'name': 'stage2', 'save': True, 'plots': True, 'device': device}
                    if s2.get('epochs') not in (None, ''): kwargs2['epochs'] = s2.get('epochs')
                    if s2.get('batch') not in (None, ''): kwargs2['batch'] = s2.get('batch')
                    if s2.get('imgsz') not in (None, ''): kwargs2['imgsz'] = s2.get('imgsz')
                    if s2.get('lr0') not in (None, ''): kwargs2['lr0'] = s2.get('lr0')
                    if s2.get('freeze') not in (None, ''): kwargs2['freeze'] = s2.get('freeze')
                    if s2.get('mosaic') not in (None, ''): kwargs2['mosaic'] = s2.get('mosaic')
                    if s2.get('close_mosaic') not in (None, ''): kwargs2['close_mosaic'] = s2.get('close_mosaic')
                    if s2.get('auto_augment') not in (None, ''): kwargs2['auto_augment'] = s2.get('auto_augment')
                    if s2.get('erasing') not in (None, ''): kwargs2['erasing'] = s2.get('erasing')
                    if s2.get('hsv_s') not in (None, ''): kwargs2['hsv_s'] = s2.get('hsv_s')
                    if s2.get('hsv_v') not in (None, ''): kwargs2['hsv_v'] = s2.get('hsv_v')
                    if s2.get('augment') not in (None, ''): kwargs2['augment'] = s2.get('augment')
                    training_status['message'] = '阶段二训练中...'
                    csv2 = os.path.join(training_dir, 'stage2', 'results.csv')
                    e2 = threading.Event()
                    t2 = threading.Thread(target=_monitor, args=(csv2, kwargs2.get('epochs'), 50, 50, e2, '阶段二训练中...'))
                    t2.daemon = True
                    t2.start()
                    def _safe_train(m, kw):
                        attempts = [{}]
                        batch_candidates = []
                        b0 = kw.get('batch')
                        if isinstance(b0, int):
                            if str(device).lower() == 'cpu':
                                batch_candidates = [1, max(1, b0//2), max(1, b0), 2, 4]
                            else:
                                batch_candidates = [b0, max(1, b0//2), 2, 1]
                        else:
                            batch_candidates = [1, 2, 4, 8] if str(device).lower() == 'cpu' else [8, 4, 2, 1]
                        for a in attempts:
                            if 'imgsz' in a:
                                kw['imgsz'] = a['imgsz']
                            for b in batch_candidates:
                                kw['batch'] = b
                                kw['workers'] = 0 if str(device).lower() == 'cpu' else 2
                                while True:
                                    try:
                                        training_status['message'] = f"阶段二训练中... imgsz={kw.get('imgsz')}, batch={kw.get('batch')}"
                                        m.train(**kw)
                                        return True
                                    except Exception as ex:
                                        msg = str(ex)
                                        if ('out of memory' in msg.lower()) or ('CUDA out of memory' in msg) or ('CUDA' in msg and 'memory' in msg.lower()):
                                            training_status['message'] = f"内存不足，尝试降级 imgsz/batch 继续... ({kw.get('imgsz')}/{kw.get('batch')})"
                                            break
                                        if 'unexpected keyword argument' in msg:
                                            import re
                                            mkey = None
                                            mm = re.search(r"unexpected keyword argument '(.*?)'", msg)
                                            if mm:
                                                mkey = mm.group(1)
                                            if mkey and mkey in kw:
                                                del kw[mkey]
                                                training_status['message'] = f"移除不支持超参: {mkey}，继续训练..."
                                                continue
                                            raise
                                        raise
                        raise RuntimeError('阶段二内存不足，降级后仍失败')
                    _safe_train(model2, kwargs2)
                    e2.set()
                    training_status['progress'] = 100
                    best2 = os.path.join(training_dir, 'stage2', 'weights', 'best.pt')
                    last2 = os.path.join(training_dir, 'stage2', 'weights', 'last.pt')
                    results = {'best_model_path': best2 if os.path.exists(best2) else (last2 if os.path.exists(last2) else ''), 'last_model_path': last2 if os.path.exists(last2) else ''}
                    training_status['results'] = results
                    training_status['message'] = '两阶段训练完成'
                    training_status['progress'] = 100
                    training_status['is_running'] = False
                except Exception as e:
                    training_status['message'] = f'两阶段训练失败: {str(e)}'
                    training_status['is_running'] = False
            threading.Thread(target=_run_two_stage).start()
            return {'success': True, 'training_id': training_id, 'message': '两阶段训练已启动'}
        except Exception as e:
            training_status['is_running'] = False
            training_status['message'] = f'训练启动失败: {str(e)}'
            return {'success': False, 'error': str(e)}

    @staticmethod
    def stop_training():
        """停止训练任务"""
        global training_status
        
        if training_status['is_running']:
            training_status['is_running'] = False
            training_status['message'] = '训练已停止'
            return {'success': True, 'message': '训练任务已停止'}
        else:
            return {'success': False, 'error': '没有正在运行的训练任务'}
    
    @staticmethod
    def get_training_status():
        """获取训练状态"""
        return training_status.copy()
    
    @staticmethod
    def get_training_history(project_path, dataset_name=None):
        """获取项目的历史训练记录（支持按数据集过滤）"""
        history = []
        base = os.path.join(project_path, "training_outputs")
        if not os.path.exists(base):
            return history
        # 遍历数据集子目录
        datasets = [dataset_name] if dataset_name else [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
        for ds in datasets:
            ds_dir = os.path.join(base, ds)
            if not os.path.isdir(ds_dir):
                continue
            for rid in os.listdir(ds_dir):
                run_dir = os.path.join(ds_dir, rid)
                cfg = os.path.join(run_dir, "training_config.json")
                if os.path.exists(cfg):
                    try:
                        with open(cfg, 'r', encoding='utf-8') as f:
                            info = json.load(f)
                            info['dataset'] = ds
                            history.append(info)
                    except Exception:
                        continue
        return history

    @staticmethod
    def list_training_runs(project_path):
        base = os.path.join(project_path, 'training_outputs')
        runs = []
        if not os.path.exists(base):
            return runs
        # 支持嵌套数据集目录结构 training_outputs/<dataset_name>/<training_id>
        for ds in sorted(os.listdir(base)):
            ds_dir = os.path.join(base, ds)
            if not os.path.isdir(ds_dir):
                continue
            for rid in sorted(os.listdir(ds_dir), reverse=True):
                run_dir = os.path.join(ds_dir, rid)
                cfg_file = os.path.join(run_dir, 'training_config.json')
                info = {'training_id': rid, 'dataset': ds}
                if os.path.exists(cfg_file):
                    try:
                        with open(cfg_file, 'r', encoding='utf-8') as f:
                            j = json.load(f)
                            info.update({
                                'start_time': j.get('start_time'),
                                'status': j.get('status'),
                                'dataset_yaml': j.get('dataset_yaml'),
                                'model_name': j.get('model_name'),
                            })
                    except Exception:
                        pass
                runs.append(info)
        return runs

    @staticmethod
    def get_latest_artifacts(project_path, training_id=None):
        base = os.path.join(project_path, 'training_outputs')
        run_dir = None
        if training_id:
            if os.path.exists(base):
                for ds in os.listdir(base):
                    parent = os.path.join(base, ds, training_id)
                    if not os.path.isdir(parent):
                        continue
                    cand = []
                    r0 = os.path.join(parent, 'run')
                    if os.path.exists(r0):
                        cand.append(r0)
                    try:
                        for c in sorted(glob.glob(os.path.join(parent, 'run*')), reverse=True):
                            if c not in cand and os.path.isdir(c):
                                cand.append(c)
                    except Exception:
                        pass
                    for c in cand:
                        w = os.path.join(c, 'weights')
                        if os.path.exists(w):
                            run_dir = c
                            break
                    if run_dir:
                        break
        else:
            if os.path.exists(base):
                for ds in sorted(os.listdir(base), reverse=True):
                    ds_dir = os.path.join(base, ds)
                    if not os.path.isdir(ds_dir):
                        continue
                    items = sorted(os.listdir(ds_dir), reverse=True)
                    for it in items:
                        parent = os.path.join(ds_dir, it)
                        if not os.path.isdir(parent):
                            continue
                        cand = []
                        r0 = os.path.join(parent, 'run')
                        if os.path.exists(r0):
                            cand.append(r0)
                        try:
                            for c in sorted(glob.glob(os.path.join(parent, 'run*')), reverse=True):
                                if c not in cand and os.path.isdir(c):
                                    cand.append(c)
                        except Exception:
                            pass
                        for c in cand:
                            w = os.path.join(c, 'weights')
                            if os.path.exists(w):
                                run_dir = c
                                break
                        if run_dir:
                            break
                    if run_dir:
                        break
        if not run_dir or not os.path.exists(run_dir):
            return {}
        artifacts = {}
        # 两阶段兼容：stage1/2/单阶段run的产物命名小差异
        weights = os.path.join(run_dir, 'weights', 'best.pt')
        weights_last = os.path.join(run_dir, 'weights', 'last.pt')
        results_png = os.path.join(run_dir, 'results.png')
        confusion = os.path.join(run_dir, 'confusion_matrix.png')
        pr_curve = os.path.join(run_dir, 'PR_curve.png')
        box_pr = os.path.join(run_dir, 'BoxPR_curve.png')
        box_p = os.path.join(run_dir, 'BoxP_curve.png')
        box_r = os.path.join(run_dir, 'BoxR_curve.png')
        f1_curve = os.path.join(run_dir, 'F1_curve.png')
        results_csv = os.path.join(run_dir, 'results.csv')
        # val批次图片在不同版本命名可能不同：val_batchX_pred/labels 或 val*.jpg
        val_batches = sorted(glob.glob(os.path.join(run_dir, 'val*batch*.*')))[:6]
        def _sz(p):
            try:
                return os.path.getsize(p) if p and os.path.exists(p) else 0
            except Exception:
                return 0
        artifacts['weights_best'] = weights if os.path.exists(weights) else ''
        artifacts['weights_last'] = weights_last if os.path.exists(weights_last) else ''
        artifacts['best_size_bytes'] = _sz(weights)
        artifacts['last_size_bytes'] = _sz(weights_last)
        artifacts['results_png'] = results_png if os.path.exists(results_png) else ''
        artifacts['confusion_matrix'] = confusion if os.path.exists(confusion) else ''
        artifacts['pr_curve'] = pr_curve if os.path.exists(pr_curve) else (box_pr if os.path.exists(box_pr) else '')
        artifacts['box_p_curve'] = box_p if os.path.exists(box_p) else ''
        artifacts['box_r_curve'] = box_r if os.path.exists(box_r) else ''
        artifacts['f1_curve'] = f1_curve if os.path.exists(f1_curve) else ''
        artifacts['results_csv'] = results_csv if os.path.exists(results_csv) else ''
        artifacts['val_batch_images'] = val_batches
        return artifacts

    @staticmethod
    def start_training_from_artifact(project_path, dataset_name='training', use_best=True, training_config=None):
        global training_status
        try:
            dataset_dir = os.path.join(project_path, dataset_name)
            dataset_yaml = None
            for y in (
                os.path.join(dataset_dir, 'dataset.yaml'),
                os.path.join(dataset_dir, 'data.yaml')
            ):
                if os.path.exists(y):
                    dataset_yaml = y
                    break
            if not dataset_yaml:
                for f in os.listdir(dataset_dir):
                    if f.endswith(('.yaml', '.yml')):
                        dataset_yaml = os.path.join(dataset_dir, f)
                        break
            if not dataset_yaml:
                return {'success': False, 'error': '未找到数据集配置文件'}

            artifacts = TrainingManager.get_latest_artifacts(project_path)
            model_path = artifacts.get('weights_best') if use_best else artifacts.get('weights_last')
            if not model_path:
                # 回退选择可用的任一权重
                model_path = artifacts.get('weights_last') or artifacts.get('weights_best')
            if not model_path or not os.path.exists(model_path):
                return {'success': False, 'error': '未找到可继续训练的权重'}

            training_output_dir = os.path.join(project_path, "training_outputs", dataset_name)
            os.makedirs(training_output_dir, exist_ok=True)
            training_id = f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            training_dir = os.path.join(training_output_dir, training_id)
            os.makedirs(training_dir, exist_ok=True)

            training_status.update({
                'is_running': True,
                'progress': 0,
                'message': '准备训练环境...',
                'start_time': datetime.now().isoformat(),
                'training_id': training_id,
                'project_path': project_path,
                'dataset_name': dataset_name,
                'model_name': 'artifact',
                'results': {}
            })

            config_file = os.path.join(training_dir, "training_config.json")
            training_info = {
                'training_id': training_id,
                'project_path': project_path,
                'dataset_name': dataset_name,
                'model_name': 'artifact',
                'model_path': model_path,
                'dataset_yaml': dataset_yaml,
                'model_config': {'name': 'artifact', 'path': model_path},
                'training_config': training_config or {},
                'start_time': training_status['start_time'],
                'status': 'running'
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(training_info, f, ensure_ascii=False, indent=2)

            import threading
            training_thread = threading.Thread(
                target=TrainingManager._run_yolo_training,
                args=(training_dir, training_info)
            )
            training_thread.start()
            return {
                'success': True,
                'training_id': training_id,
                'message': '继续训练任务已启动'
            }
        except Exception as e:
            training_status['is_running'] = False
            training_status['message'] = f'继续训练启动失败: {str(e)}'
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_latest_run_dir(project_path):
        base = os.path.join(project_path, 'training_outputs')
        if not os.path.exists(base):
            return None, None
        items = sorted(os.listdir(base), reverse=True)
        for it in items:
            pr = os.path.join(base, it, 'run')
            if os.path.exists(pr):
                return pr, it
        return None, None

    @staticmethod
    def resume_last_run(project_path, dataset_name='training'):
        global training_status
        try:
            run_dir, run_id = TrainingManager.get_latest_run_dir(project_path)
            if not run_dir:
                return {'success': False, 'error': '未找到可续跑的训练记录'}
            parent = os.path.dirname(run_dir)
            name = os.path.basename(run_dir)
            weights_last = os.path.join(run_dir, 'weights', 'last.pt')
            if not os.path.exists(weights_last):
                return {'success': False, 'error': '未找到last.pt权重'}
            dataset_dir = os.path.join(project_path, dataset_name)
            dataset_yaml = None
            for y in (
                os.path.join(dataset_dir, 'dataset.yaml'),
                os.path.join(dataset_dir, 'data.yaml')
            ):
                if os.path.exists(y):
                    dataset_yaml = y
                    break
            if not dataset_yaml:
                for f in os.listdir(dataset_dir):
                    if f.endswith(('.yaml', '.yml')):
                        dataset_yaml = os.path.join(dataset_dir, f)
                        break
            if not dataset_yaml:
                return {'success': False, 'error': '未找到数据集配置文件'}

            training_status.update({
                'is_running': True,
                'progress': 0,
                'message': '准备续跑...',
                'start_time': datetime.now().isoformat(),
                'training_id': run_id,
                'project_path': project_path,
                'dataset_name': dataset_name,
                'model_name': 'resume',
                'results': {}
            })

            device = get_device()
            yolo_bin = os.path.join(os.environ.get('VIRTUAL_ENV') or os.path.dirname(sys.executable), 'bin', 'yolo')
            if not os.path.exists(yolo_bin):
                yolo_bin = os.path.join(PROJECT_ROOT, 'myenv', 'bin', 'yolo')
            cmd = [
                yolo_bin,
                'train',
                f"data={dataset_yaml}",
                f"model={weights_last}",
                'resume=True',
                f"project={parent}",
                f"name={name}",
                f"device={device}",
                'save=True',
                'plots=True'
            ]
            if str(device).lower() == 'cpu':
                cmd.append('batch=1')
                cmd.append('workers=0')
            p = None
            try:
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            except FileNotFoundError:
                try:
                    from ultralytics import YOLO
                    model = YOLO(weights_last)
                    kwargs = {
                        'data': dataset_yaml,
                        'project': parent,
                        'name': name,
                        'save': True,
                        'plots': True,
                        'device': device,
                        'resume': True,
                        'amp': False,
                    }
                    if str(device).lower() == 'cpu':
                        kwargs['batch'] = 1
                        kwargs['workers'] = 0
                    model.train(**kwargs)
                except Exception as e:
                    training_status['message'] = f'续跑失败: {str(e)}'
                    training_status['is_running'] = False
                    return {'success': False, 'error': str(e)}
            start_time = time.time()
            last_line = ''
            for line in p.stdout:
                if not training_status['is_running']:
                    try:
                        p.terminate()
                    except Exception:
                        pass
                    break
                last_line = line.strip()
                training_status['message'] = last_line[:200]
            if p:
                p.wait()
            weights_best = os.path.join(run_dir, 'weights', 'best.pt')
            results_csv = os.path.join(run_dir, 'results.csv')
            results_png = os.path.join(run_dir, 'results.png')
            metrics = {}
            if os.path.exists(results_csv):
                try:
                    with open(results_csv, 'r') as f:
                        rows = list(csv.DictReader(f))
                        if rows:
                            metrics = rows[-1]
                except Exception:
                    pass
            results = {
                'best_model_path': weights_best if os.path.exists(weights_best) else weights_last,
                'last_model_path': weights_last,
                'results_csv': results_csv if os.path.exists(results_csv) else '',
                'results_png': results_png if os.path.exists(results_png) else '',
                'metrics': metrics,
                'training_dir': run_dir,
                'training_time': int(time.time() - start_time)
            }
            training_status['results'] = results
            training_status['message'] = '续跑完成'
            training_status['progress'] = 100
            training_status['is_running'] = False
            return {'success': True, 'training_id': run_id, 'message': '续跑完成'}
        except Exception as e:
            training_status['message'] = f'续跑失败: {str(e)}'
            training_status['is_running'] = False
            return {'success': False, 'error': str(e)}

    @staticmethod
    def evaluate_model(project_path, training_id=None, split='val'):
        base = os.path.join(project_path, 'training_outputs')
        artifacts = TrainingManager.get_latest_artifacts(project_path, training_id)
        weights = artifacts.get('weights_best') or artifacts.get('weights_last')
        if not weights:
            return {'success': False, 'error': '未找到最佳模型文件'}
        dataset_yaml = None
        cfg_path = None
        if training_id:
            if os.path.exists(base):
                for ds in os.listdir(base):
                    p = os.path.join(base, ds, training_id, 'training_config.json')
                    if os.path.exists(p):
                        cfg_path = p
                        break
        else:
            # 找最新一次训练配置
            if os.path.exists(base):
                items = sorted(os.listdir(base), reverse=True)
                for it in items:
                    p = os.path.join(base, it, 'training_config.json')
                    if os.path.exists(p):
                        cfg_path = p
                        break
        if cfg_path and os.path.exists(cfg_path):
            try:
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                    dataset_yaml = info.get('dataset_yaml')
            except Exception:
                pass
        if not dataset_yaml:
            # 回退到项目training目录
            training_dir = os.path.join(project_path, 'training')
            for y in ('dataset.yaml', 'data.yaml'):
                p = os.path.join(training_dir, y)
                if os.path.exists(p):
                    dataset_yaml = p
                    break
        if not dataset_yaml:
            try:
                rd = artifacts.get('training_dir') or ''
                if rd:
                    ds_name = os.path.basename(os.path.dirname(os.path.dirname(rd)))
                    ds_root = os.path.join(project_path, 'training', ds_name)
                    for y in ('dataset.yaml', 'data.yaml'):
                        p = os.path.join(ds_root, y)
                        if os.path.exists(p):
                            dataset_yaml = p
                            break
            except Exception:
                pass
        if not dataset_yaml:
            return {'success': False, 'error': '未找到数据集配置文件'}

        # 运行评估（验证/测试）
        run_dir = os.path.dirname(artifacts.get('results_csv') or artifacts.get('results_png') or os.path.dirname(weights))
        if not os.path.exists(run_dir):
            try:
                # 当 run 被清空但存在 run2 等目录时，回退到包含权重的 run*
                parent = os.path.dirname(run_dir)
                cands = sorted(glob.glob(os.path.join(parent, 'run*')), reverse=True)
                for c in cands:
                    if os.path.isdir(c) and os.path.exists(os.path.join(c, 'weights')):
                        run_dir = c
                        break
            except Exception:
                pass
        try:
            yolo_bin = os.path.join(os.environ.get('VIRTUAL_ENV') or os.path.dirname(sys.executable), 'bin', 'yolo')
            if not os.path.exists(yolo_bin):
                yolo_bin = os.path.join(PROJECT_ROOT, 'myenv', 'bin', 'yolo')
            eval_cmd = [
                yolo_bin, 'val',
                f'data={dataset_yaml}',
                f'model={weights}',
                f'split={split}',
                'save=True',
                'plots=True',
                'exist_ok=True'
            ]
            subprocess.run(eval_cmd, check=True)
        except FileNotFoundError:
            try:
                from ultralytics import YOLO
                m = YOLO(weights)
                m.val(data=dataset_yaml, split=split, save=True, plots=True)
            except Exception as e:
                return {'success': False, 'error': f'评估失败: {str(e)}'}

        # 查找最新生成的评估图
        images = []
        for name in ['PR_curve.png', 'F1_curve.png', 'confusion_matrix.png', 'results.png', 'BoxPR_curve.png', 'BoxF1_curve.png']:
            p = os.path.join(run_dir, name)
            if os.path.exists(p):
                images.append(p)

        metrics = {}
        csv_path = os.path.join(run_dir, 'results.csv')
        if os.path.exists(csv_path):
            try:
                with open(csv_path, 'r') as f:
                    rows = list(csv.DictReader(f))
                    if rows:
                        metrics = rows[-1]
            except Exception:
                pass
        return {'success': True, 'metrics': metrics, 'images': images}
        
        # 按时间排序
        history.sort(key=lambda x: x.get('start_time', ''), reverse=True)
        return history

    @staticmethod
    def start_evaluate_async(project_path, split='val'):
        global eval_status
        try:
            eval_status.update({'is_running': True, 'progress': 0, 'message': '准备评估...', 'start_time': datetime.now().isoformat(), 'results': {}})
            def _run():
                try:
                    base = os.path.join(project_path, 'training_outputs')
                    artifacts = TrainingManager.get_latest_artifacts(project_path)
                    weights = artifacts.get('weights_best') or artifacts.get('weights_last')
                    if not weights:
                        eval_status.update({'is_running': False, 'message': '未找到最佳模型文件'});
                        return
                    dataset_yaml = None
                    cfg_path = None
                    if os.path.exists(base):
                        items = sorted(os.listdir(base), reverse=True)
                        for it in items:
                            p = os.path.join(base, it, 'training_config.json')
                            if os.path.exists(p):
                                cfg_path = p; break
                    if cfg_path and os.path.exists(cfg_path):
                        try:
                            with open(cfg_path, 'r', encoding='utf-8') as f:
                                info = json.load(f)
                                dataset_yaml = info.get('dataset_yaml')
                        except Exception:
                            pass
                    if not dataset_yaml:
                        training_dir = os.path.join(project_path, 'training')
                        for y in ('dataset.yaml', 'data.yaml'):
                            p = os.path.join(training_dir, y)
                            if os.path.exists(p):
                                dataset_yaml = p; break
                    if not dataset_yaml:
                        eval_status.update({'is_running': False, 'message': '未找到数据集配置文件'});
                        return

                    eval_cmd = [
                        'yolo', 'val',
                        f'data={dataset_yaml}',
                        f'model={weights}',
                        f'split={split}',
                        'save=True',
                        'plots=True'
                    ]
                    p = None
                    try:
                        p = subprocess.Popen(eval_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    except FileNotFoundError:
                        from ultralytics import YOLO
                        m = YOLO(weights)
                        m.val(data=dataset_yaml, split=split, save=True, plots=True)
                        eval_status.update({'progress': 100, 'message': '评估完成', 'is_running': False})
                        return
                    last_line = ''
                    for line in p.stdout:
                        last_line = line.strip()
                        eval_status['message'] = last_line[:200]
                        try:
                            m = re.search(r'\b(\d+)\s*/\s*(\d+)\b', last_line)
                            if m:
                                cur = int(m.group(1)); tot = int(m.group(2));
                                if tot > 0:
                                    eval_status['progress'] = max(eval_status['progress'], min(100, int(cur * 100 / tot)))
                        except Exception:
                            pass
                    if p:
                        p.wait()
                    run_dir = os.path.dirname(artifacts.get('results_csv') or artifacts.get('results_png') or os.path.dirname(weights))
                    images = []
                    for name in ['PR_curve.png', 'F1_curve.png', 'confusion_matrix.png', 'results.png']:
                        pp = os.path.join(run_dir, name)
                        if os.path.exists(pp):
                            images.append(pp)
                    metrics = {}
                    csv_path = os.path.join(run_dir, 'results.csv')
                    if os.path.exists(csv_path):
                        try:
                            with open(csv_path, 'r') as f:
                                rows = list(csv.DictReader(f))
                                if rows:
                                    metrics = rows[-1]
                        except Exception:
                            pass
                    eval_status.update({'results': {'metrics': metrics, 'images': images}, 'progress': 100, 'message': '评估完成', 'is_running': False})
                except Exception as e:
                    eval_status.update({'message': f'评估失败: {str(e)}', 'is_running': False})
            threading.Thread(target=_run).start()
            return {'success': True, 'message': '评估任务已启动'}
        except Exception as e:
            eval_status.update({'message': f'评估启动失败: {str(e)}', 'is_running': False})
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_evaluate_status():
        return eval_status.copy()

class ExportManager:
    @staticmethod
    def build_calibration_subset(project_path, dataset_name='training', training_id=None, per_class=20, max_images=200, dataset_yaml=None):
        dataset_dir = os.path.join(project_path, dataset_name)
        y = {}
        if dataset_yaml and os.path.exists(dataset_yaml):
            try:
                with open(dataset_yaml, 'r', encoding='utf-8') as f:
                    y = yaml.safe_load(f) or {}
            except Exception:
                y = {}
        else:
            for yfile in (os.path.join(dataset_dir, 'dataset.yaml'), os.path.join(dataset_dir, 'data.yaml')):
                if os.path.exists(yfile):
                    dataset_yaml = yfile
                    try:
                        with open(yfile, 'r', encoding='utf-8') as f:
                            y = yaml.safe_load(f) or {}
                    except Exception:
                        y = {}
                    break

        dataset_base = os.path.dirname(dataset_yaml) if dataset_yaml else dataset_dir
        base_path = y.get('path') or dataset_base
        def _abspath(p):
            if not p:
                return None
            return p if os.path.isabs(p) else os.path.join(base_path, p)
        # 严格遵循现有规范：仅使用 images/train 作为校准图片来源
        train_images_path = _abspath(y.get('train'))
        if not train_images_path or not os.path.exists(train_images_path):
            alt_train = os.path.join(base_path, 'images', 'train')
            if os.path.exists(alt_train):
                train_images_path = alt_train
            else:
                found = None
                for root, dirs, _ in os.walk(base_path):
                    if 'images' in dirs and os.path.exists(os.path.join(root, 'images', 'train')):
                        found = os.path.join(root, 'images', 'train')
                        break
                train_images_path = found
        def _infer_labels(images_path):
            if not images_path:
                return None
            return images_path.replace(os.sep + 'images' + os.sep, os.sep + 'labels' + os.sep)
        # 严格规范：标签目录固定 labels/train（可选），缺失时按图片均匀采样
        labels_train = os.path.join(base_path, 'labels', 'train')
        labels_train = labels_train if os.path.exists(labels_train) else None

        names = y.get('names') or []
        nc = y.get('nc') or (len(names) if names else None)

        class_to_images = {}
        image_to_classes = {}
        if labels_train:
            for root, _, files in os.walk(labels_train):
                for f in files:
                    if not f.endswith('.txt'):
                        continue
                    lbl_path = os.path.join(root, f)
                    rel_lbl = os.path.relpath(lbl_path, labels_train)
                    img_rel = os.path.splitext(rel_lbl)[0] + '.jpg'
                    image_to_classes.setdefault(img_rel, set())
                    try:
                        with open(lbl_path, 'r', encoding='utf-8') as lf:
                            for line in lf:
                                parts = line.strip().split()
                                if not parts:
                                    continue
                                cid = int(parts[0])
                                image_to_classes[img_rel].add(cid)
                    except Exception:
                        continue
        else:
            if not train_images_path or not os.path.exists(train_images_path):
                raise FileNotFoundError('未找到用于校准的图片目录（images/train）')
            for root, _, files in os.walk(train_images_path):
                for f in files:
                    if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                        rel_img = os.path.relpath(os.path.join(root, f), train_images_path)
                        image_to_classes.setdefault(rel_img, set())

        for img_rel, classes in image_to_classes.items():
            for cid in classes:
                class_to_images.setdefault(cid, set()).add(img_rel)

        selected = set()
        cids = sorted(class_to_images.keys())
        rounds = 0
        while rounds < per_class and len(selected) < max_images and cids:
            for cid in cids:
                pool = class_to_images.get(cid, set())
                pick = next((p for p in pool if p not in selected), None)
                if pick:
                    selected.add(pick)
                if len(selected) >= max_images:
                    break
            rounds += 1
        if len(selected) < max_images:
            # 频次回填或简单遍历补齐
            freq_sorted = sorted(image_to_classes.items(), key=lambda kv: len(kv[1]), reverse=True)
            for img_rel, _ in freq_sorted:
                if img_rel not in selected:
                    selected.add(img_rel)
                if len(selected) >= max_images:
                    break

        base_out = os.path.join(project_path, 'training_outputs')
        if training_id is None:
            _, training_id = TrainingManager.get_latest_run_dir(project_path)
            if training_id is None:
                training_id = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        calib_root = os.path.join(base_out, training_id, 'calibration', ts)
        img_out = os.path.join(calib_root, 'images', 'train')
        os.makedirs(img_out, exist_ok=True)
        lbl_out = None
        if labels_train:
            lbl_out = os.path.join(calib_root, 'labels', 'train')
            os.makedirs(lbl_out, exist_ok=True)

        for img_rel in selected:
            src_img = os.path.join(train_images_path, img_rel)
            dst_img = os.path.join(img_out, img_rel)
            os.makedirs(os.path.dirname(dst_img), exist_ok=True)
            if os.path.exists(src_img):
                shutil.copy2(src_img, dst_img)
            if lbl_out:
                src_lbl = os.path.join(labels_train, os.path.splitext(img_rel)[0] + '.txt')
                dst_lbl = os.path.join(lbl_out, os.path.splitext(img_rel)[0] + '.txt')
                os.makedirs(os.path.dirname(dst_lbl), exist_ok=True)
                if os.path.exists(src_lbl):
                    shutil.copy2(src_lbl, dst_lbl)

        data_yaml = {
            'path': calib_root,
            'train': os.path.join('images', 'train'),
            'val': os.path.join('images', 'train'),
        }
        if names:
            data_yaml['names'] = names
        if nc is not None:
            data_yaml['nc'] = nc
        calib_yaml_path = os.path.join(calib_root, 'data.yaml')
        with open(calib_yaml_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data_yaml, f, allow_unicode=True)
        return calib_yaml_path, calib_root

    @staticmethod
    def export_model(project_path, training_id=None, format='onnx', half=False, int8=False, imgsz=None, per_class=20, max_images=200, weights_path=None):
        from ultralytics import YOLO
        global export_status
        export_status.update({'is_running': True, 'progress': 0, 'message': '准备导出...', 'start_time': datetime.now().isoformat(), 'results': {}})
        try:
            artifacts = TrainingManager.get_latest_artifacts(project_path, training_id)
            weights = weights_path or artifacts.get('weights_best') or artifacts.get('weights_last')
            if not weights or not os.path.exists(weights):
                raise FileNotFoundError('未找到可导出的权重')
            run_dir = artifacts.get('training_dir')
            if not run_dir:
                wd = os.path.dirname(weights)
                run_dir = os.path.dirname(wd) if os.path.basename(wd) == 'weights' else wd
            # 统一覆盖到 latest 目录，不产生版本
            export_dir = os.path.join(project_path, 'training_outputs', 'export', 'latest')
            if os.path.exists(export_dir):
                try:
                    shutil.rmtree(export_dir)
                except Exception:
                    pass
            os.makedirs(export_dir, exist_ok=True)

            export_status['message'] = '加载模型...'
            model = YOLO(weights)
            args = {'format': format, 'half': bool(half), 'imgsz': imgsz}
            if int8:
                export_status['message'] = '构建校准集...'
                run_parent = os.path.basename(os.path.dirname(run_dir))
                cfg_path = os.path.join(os.path.dirname(run_dir), 'training_config.json')
                dy = None
                if os.path.exists(cfg_path):
                    try:
                        with open(cfg_path, 'r', encoding='utf-8') as f:
                            info = json.load(f)
                            dy = info.get('dataset_yaml')
                    except Exception:
                        pass
                calib_yaml, calib_root = ExportManager.build_calibration_subset(project_path, training_id=run_parent, per_class=per_class, max_images=max_images, dataset_yaml=dy)
                export_status['message'] = f'构建校准集完成: {calib_yaml}'
                args.update({'format': 'openvino', 'int8': True, 'data': calib_yaml})
            export_status['message'] = '执行导出...'
            out = model.export(**{k: v for k, v in args.items() if v is not None})
            export_status['message'] = '导出完成'
            # 清理校准集（仅在 INT8 构建时存在）
            try:
                if int8:
                    shutil.rmtree(calib_root, ignore_errors=True)
            except Exception:
                pass
            export_status['progress'] = 100
            # 规范化结果
            results = {}
            if isinstance(out, (list, tuple)):
                files = [str(x) for x in out]
            else:
                files = [str(out)]
            # 复制导出文件到 latest 目录
            copied = []
            for fp in files:
                if not fp:
                    continue
                if os.path.isdir(fp):
                    # 目录型（如 OpenVINO），复制整个目录内容
                    dst = os.path.join(export_dir, os.path.basename(fp))
                    try:
                        shutil.copytree(fp, dst)
                    except Exception:
                        os.makedirs(dst, exist_ok=True)
                        for root, _, fs in os.walk(fp):
                            for f in fs:
                                srcf = os.path.join(root, f)
                                rel = os.path.relpath(srcf, fp)
                                dstf = os.path.join(dst, rel)
                                os.makedirs(os.path.dirname(dstf), exist_ok=True)
                                shutil.copy2(srcf, dstf)
                    copied.append(dst)
                else:
                    dst = os.path.join(export_dir, os.path.basename(fp))
                    shutil.copy2(fp, dst)
                    copied.append(dst)
            # 选择主模型文件供评估使用
            primary = ''
            for c in copied:
                if c.endswith('.onnx'):
                    primary = c; break
                if c.endswith('.xml'):
                    primary = c; break
            # 统计大小
            def _sz(p):
                try:
                    if os.path.isdir(p):
                        total = 0
                        for root, _, fs in os.walk(p):
                            for f in fs:
                                total += os.path.getsize(os.path.join(root, f))
                        return total
                    return os.path.getsize(p)
                except Exception:
                    return 0
            results['files'] = copied
            results['primary_model_path'] = primary
            results['total_size_bytes'] = sum(_sz(p) for p in copied)
            results['export_dir'] = export_dir
            export_status['results'] = results
            return {'success': True, 'export_dir': export_dir, 'results': results}
        except Exception as e:
            export_status['message'] = f'导出失败: {str(e)}'
            export_status['is_running'] = False
            return {'success': False, 'error': str(e)}
        finally:
            export_status['is_running'] = False

    @staticmethod
    def list_exports(project_path, training_id=None):
        base = os.path.join(project_path, 'training_outputs')
        items = []
        if not os.path.exists(base):
            return items

        global_latest = os.path.join(base, 'export', 'latest')
        if os.path.exists(global_latest):
            files = []
            for root, _, fs in os.walk(global_latest):
                for f in fs:
                    files.append(os.path.join(root, f))
            primary = ''
            for f in files:
                if f.endswith('.onnx'):
                    primary = f; break
                if f.endswith('.xml'):
                    primary = f; break
            def _sz(p):
                try:
                    return os.path.getsize(p)
                except Exception:
                    return 0
            total = sum(_sz(p) for p in files)
            items.append({'training_id': training_id or 'latest', 'ts': 'latest', 'files': files, 'primary_model_path': primary, 'export_dir': global_latest, 'total_size_bytes': total})

        for ds in os.listdir(base):
            ds_dir = os.path.join(base, ds)
            if not os.path.isdir(ds_dir):
                continue
            if training_id:
                latest = os.path.join(ds_dir, training_id, 'export', 'latest')
                if not os.path.exists(latest):
                    continue
                files = []
                for root, _, fs in os.walk(latest):
                    for f in fs:
                        files.append(os.path.join(root, f))
                primary = ''
                for f in files:
                    if f.endswith('.onnx'):
                        primary = f; break
                    if f.endswith('.xml'):
                        primary = f; break
                def _sz2(p):
                    try:
                        return os.path.getsize(p)
                    except Exception:
                        return 0
                total = sum(_sz2(p) for p in files)
                items.append({'training_id': training_id, 'ts': 'latest', 'files': files, 'primary_model_path': primary, 'export_dir': latest, 'total_size_bytes': total})
            else:
                latest = os.path.join(ds_dir, 'export', 'latest')
                if not os.path.exists(latest):
                    continue
                files = []
                for root, _, fs in os.walk(latest):
                    for f in fs:
                        files.append(os.path.join(root, f))
                primary = ''
                for f in files:
                    if f.endswith('.onnx'):
                        primary = f; break
                    if f.endswith('.xml'):
                        primary = f; break
                def _sz3(p):
                    try:
                        return os.path.getsize(p)
                    except Exception:
                        return 0
                total = sum(_sz3(p) for p in files)
                items.append({'training_id': ds, 'ts': 'latest', 'files': files, 'primary_model_path': primary, 'export_dir': latest, 'total_size_bytes': total})

        return items



@app.route('/api/training/start_two_stage', methods=['POST'])
def api_start_two_stage():
    return jsonify({'success': False, 'error': '两阶段训练已禁用'})

        
@app.route('/api/model/export', methods=['POST'])
def api_model_export():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        training_id = data.get('training_id')
        format_ = data.get('format', 'onnx')
        half = bool(data.get('half_precision'))
        int8 = bool(data.get('int8_quant'))
        imgsz = data.get('imgsz')
        per_class = int(data.get('per_class', 20))
        max_images = int(data.get('max_images', 200))
        weights_path = data.get('weights_path')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        export_id = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        export_status.update({'export_id': export_id, 'is_running': True, 'progress': 0, 'message': '启动导出...'})
        th = threading.Thread(target=lambda: ExportManager.export_model(project_path, training_id, format_, half, int8, imgsz, per_class, max_images, weights_path))
        th.start()
        return jsonify({'success': True, 'export_id': export_id, 'message': '导出任务已启动'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/model/export/status')
def api_model_export_status():
    try:
        return jsonify({'success': True, 'status': export_status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/model/exports')
def api_model_exports():
    try:
        project_path = request.args.get('project_path')
        training_id = request.args.get('training_id')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        items = ExportManager.list_exports(project_path, training_id)
        def as_url(p):
            return f"/api/file?path={p}"
        for it in items:
            it['files'] = [as_url(p) for p in it['files']]
        return jsonify({'success': True, 'exports': items})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/')
def index():
    """主页面"""
    projects = ProjectManager.scan_projects()
    models = ModelManager.get_pretrained_models()
    
    return render_template('dataset_tool.html', 
                         projects=projects,
                         models=models)

@app.route('/api/projects')
def api_projects():
    """获取项目列表"""
    try:
        projects = ProjectManager.scan_projects()
        return jsonify({
            'success': True,
            'projects': projects
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/training/start', methods=['POST'])
def api_start_training():
    """开始训练任务"""
    try:
        data = request.get_json()
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        model_name = data.get('model_name')
        training_config = data.get('training_config', {})
        dataset_path = data.get('dataset_path')
        
        result = TrainingManager.start_training(project_path, dataset_name, model_name, training_config, dataset_path)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/training/stop', methods=['POST'])
def api_stop_training():
    """停止训练任务"""
    try:
        global training_status
        if training_status.get('is_running'):
            training_status['is_running'] = False
            training_status['message'] = '训练已停止'
            return jsonify({'success': True, 'message': '训练任务已停止'})
        else:
            return jsonify({'success': False, 'error': '没有正在运行的训练任务'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/training/status')
def api_training_status():
    """获取训练状态"""
    try:
        status = training_status.copy()
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/training/history')
def api_training_history():
    """获取训练历史"""
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        history = TrainingManager.get_training_history(project_path, dataset_name)
        return jsonify({
            'success': True,
            'history': history
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/models')
def api_models():
    """获取预训练模型列表"""
    try:
        models = ModelManager.get_pretrained_models()
        return jsonify({
            'success': True,
            'models': models
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/training/artifacts')
def api_training_artifacts():
    try:
        project_path = request.args.get('project_path')
        training_id = request.args.get('training_id')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        artifacts = TrainingManager.get_latest_artifacts(project_path, training_id)
        metrics = {}
        csv_path = artifacts.get('results_csv')
        if csv_path and os.path.exists(csv_path):
            try:
                with open(csv_path, 'r') as f:
                    rows = list(csv.DictReader(f))
                    if rows:
                        metrics = rows[-1]
            except Exception:
                pass
        def url_for_path(p):
            return f"/api/file?path={p}" if p else ''
        def to_url(v):
            if isinstance(v, str):
                return url_for_path(v)
            if isinstance(v, (list, tuple)):
                return [url_for_path(x) for x in v]
            return v
        artifacts = {k: to_url(v) for k, v in artifacts.items()}
        return jsonify({'success': True, 'artifacts': artifacts, 'metrics': metrics})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 统一数据集接口：返回 training/ 下所有以 datasets* 命名的子目录
@app.route('/api/datasets')
def api_datasets():
    try:
        project_path = request.args.get('project_path')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        info = ProjectManager.load_project_info(project_path)
        dsets = info.get('datasets', {}) if info else {}
        return jsonify({'success': True, 'datasets': {'trainable': dsets.get('trainable', [])}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 数据集详情
@app.route('/api/dataset/info')
def api_dataset_info():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_path = os.path.join(project_path, 'training', dataset_name)
        if not os.path.isdir(ds_path):
            # 兼容 dataset_name 传入完整路径或非标准命名
            alt = os.path.join(project_path, 'training')
            for entry in os.listdir(alt):
                if entry.startswith('datasets') and os.path.isdir(os.path.join(alt, entry)):
                    if os.path.basename(os.path.join(alt, entry)) == dataset_name:
                        ds_path = os.path.join(alt, entry)
                        break
        info = ProjectManager.analyze_training_structure(ds_path) or {}
        names = []
        nc = None
        yfile = None
        for fn in ('dataset.yaml', 'data.yaml'):
            p = os.path.join(ds_path, fn)
            if os.path.exists(p):
                yfile = p
                break
        if not yfile:
            for f in os.listdir(ds_path):
                if f.endswith(('.yaml', '.yml')):
                    yfile = os.path.join(ds_path, f)
                    break
        if yfile and os.path.exists(yfile):
            try:
                with open(yfile, 'r', encoding='utf-8') as f:
                    y = yaml.safe_load(f) or {}
                n = y.get('names')
                if isinstance(n, dict):
                    names = [n[k] for k in sorted(n.keys(), key=lambda x: int(x))]
                elif isinstance(n, list):
                    names = n
                nc = y.get('nc')
            except Exception:
                pass
        info['names'] = names
        if nc is not None:
            info['nc'] = nc
        return jsonify({'success': True, 'info': info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 数据集图片分页
@app.route('/api/dataset/images')
def api_dataset_images():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        split = request.args.get('split', 'train')
        offset = int(request.args.get('offset', '0'))
        limit = int(request.args.get('limit', '50'))
        classes_param = request.args.get('classes', '')
        mode = request.args.get('mode', 'include')
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        base = os.path.join(ds_root, split, 'images')
        auto_lbl_base = os.path.join(ds_root, 'auto_labels', split)
        lbl_dir = os.path.join(ds_root, split, 'labels')
        files = []
        total = 0
        if os.path.exists(base):
            all = []
            for root, _, fs in os.walk(base):
                for f in fs:
                    if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                        all.append(os.path.join(root, f))
            if classes_param:
                class_ids = set()
                yfile = None
                for fn in ('dataset.yaml', 'data.yaml'):
                    p = os.path.join(ds_root, fn)
                    if os.path.exists(p):
                        yfile = p
                        break
                names = []
                if yfile and os.path.exists(yfile):
                    try:
                        with open(yfile, 'r', encoding='utf-8') as f:
                            y = yaml.safe_load(f) or {}
                        n = y.get('names')
                        if isinstance(n, dict):
                            names = [n[k] for k in sorted(n.keys(), key=lambda x: int(x))]
                        elif isinstance(n, list):
                            names = n
                    except Exception:
                        names = []
                tokens = [t.strip() for t in classes_param.split(',') if t.strip()]
                for t in tokens:
                    if t.isdigit():
                        try:
                            class_ids.add(int(t))
                        except Exception:
                            pass
                    else:
                        try:
                            if names:
                                for i, nm in enumerate(names):
                                    if str(nm) == t:
                                        class_ids.add(i)
                                        break
                        except Exception:
                            pass
                filtered = []
                for p in all:
                    rel = os.path.relpath(p, base)
                    lblp = os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')
                    has = False
                    if os.path.exists(lblp):
                        try:
                            with open(lblp, 'r', encoding='utf-8') as f:
                                for line in f:
                                    s = line.strip().split()
                                    if not s:
                                        continue
                                    try:
                                        cid = int(float(s[0]))
                                    except Exception:
                                        continue
                                    if cid in class_ids:
                                        has = True
                                        break
                        except Exception:
                            has = False
                    if mode == 'include':
                        if has:
                            filtered.append(p)
                    else:
                        if not has:
                            filtered.append(p)
                all = filtered
            total = len(all)
            page = all[offset:offset+limit]
            files = []
            for p in page:
                rel = os.path.relpath(p, base)
                lbl = os.path.join(auto_lbl_base, os.path.splitext(rel)[0] + '.txt')
                files.append({'url': f"/api/file?path={p}", 'path': p, 'pending': os.path.exists(lbl)})
        return jsonify({'success': True, 'images': files, 'total': total})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 未标注图片列表
@app.route('/api/annotation/missing')
def api_annotation_missing():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        split = request.args.get('split', 'train')
        offset = int(request.args.get('offset', '0'))
        limit = int(request.args.get('limit', '50'))
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, split, 'labels')
        items = []
        if os.path.exists(img_dir):
            all_imgs = []
            for root, _, fs in os.walk(img_dir):
                for f in fs:
                    if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                        p = os.path.join(root, f)
                        rel = os.path.relpath(p, img_dir)
                        lbl = os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')
                        if not os.path.exists(lbl):
                            all_imgs.append(p)
            total = len(all_imgs)
            page = all_imgs[offset:offset+limit]
            items = [f"/api/file?path={p}" for p in page]
            return jsonify({'success': True, 'images': items, 'total': total})
        return jsonify({'success': True, 'images': [], 'total': 0})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 自动标注
@app.route('/api/auto_annotate', methods=['POST'])
def api_auto_annotate():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        image_path = data.get('image_path')
        threshold = float(data.get('threshold', 0.25))
        max_boxes = int(data.get('max_boxes', 100))
        if not project_path or not dataset_name or not image_path:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        model = _get_auto_annotate_model(project_path, prefer_project_best=True)
        if model is None:
            return jsonify({'success': False, 'error': '自动标注模型不可用'})
        # 运行推理
        res = model.predict(image_path, conf=threshold, max_det=max_boxes, verbose=False)
        boxes = []
        try:
            out = res[0]
            for b in out.boxes:
                xyxy = b.xyxy[0].tolist()
                cls = int(b.cls.item()) if hasattr(b, 'cls') else 0
                conf = float(b.conf.item()) if hasattr(b, 'conf') else 0.0
                boxes.append({'class': cls, 'conf': conf, 'x1': xyxy[0], 'y1': xyxy[1], 'x2': xyxy[2], 'y2': xyxy[3]})
        except Exception:
            boxes = []
        return jsonify({'success': True, 'boxes': boxes})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 批量自动标注
@app.route('/api/auto_annotate/batch', methods=['POST'])
def api_auto_annotate_batch():
    try:
        global batch_status
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        split = data.get('split', 'train')
        model_path = data.get('model_path')
        conf = float(data.get('conf', 0.25))
        max_det = int(data.get('max_det', 200))
        batch_size = int(data.get('batch_size', 1))
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        from ultralytics import YOLO
        model = YOLO(model_path) if model_path else _get_auto_annotate_model(project_path, prefer_project_best=True)
        if model is None:
            return jsonify({'success': False, 'error': '模型不可用'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, 'auto_labels', split)
        os.makedirs(lbl_dir, exist_ok=True)
        images = []
        for root, _, fs in os.walk(img_dir):
            for f in fs:
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    images.append(os.path.join(root, f))
        images.sort()
        total = len(images)
        batch_status.update({'is_running': True, 'progress': 0, 'message': '执行批量自动标注...'})
        added = 0
        pending = 0
        def to_lbl(p):
            rel = os.path.relpath(p, img_dir)
            return os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')
        # 批量推理
        for i in range(0, len(images), batch_size):
            batch = images[i:i+batch_size]
            try:
                results = model.predict(batch, conf=conf, max_det=max_det, verbose=False)
            except Exception:
                continue
            for bi, res in enumerate(results):
                img_path = batch[bi]
                auto_lbl_path = to_lbl(img_path)
                boxes = []
                try:
                    for b in res.boxes:
                        xyxy = b.xyxy[0].tolist()
                        cls = int(b.cls.item()) if hasattr(b, 'cls') else 0
                        boxes.append({'class': cls, 'x1': xyxy[0], 'y1': xyxy[1], 'x2': xyxy[2], 'y2': xyxy[3]})
                except Exception:
                    boxes = []
                if not boxes:
                    continue
                # 写入到 auto_labels（不修改人工 labels）
                try:
                    from PIL import Image
                    with Image.open(img_path) as im:
                        w, h = im.size
                except Exception:
                    w, h = 1, 1
                # 读取已有人工与自动标签用于去重
                def _read_yolo(file_path):
                    arr = []
                    if not os.path.exists(file_path):
                        return arr
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            for ln in f:
                                parts = ln.strip().split()
                                if len(parts) >= 5:
                                    cid = int(float(parts[0]))
                                    cx = float(parts[1]) * w
                                    cy = float(parts[2]) * h
                                    ww = float(parts[3]) * w
                                    hh = float(parts[4]) * h
                                    x1 = max(0.0, cx - ww/2)
                                    y1 = max(0.0, cy - hh/2)
                                    x2 = min(float(w), cx + ww/2)
                                    y2 = min(float(h), cy + hh/2)
                                    arr.append({'class': cid, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
                    except Exception:
                        return arr
                    return arr
                manual_lbl = os.path.join(ds_root, 'labels', split, os.path.splitext(os.path.relpath(img_path, img_dir))[0] + '.txt')
                exist_manual = _read_yolo(manual_lbl)
                exist_auto = _read_yolo(auto_lbl_path)
                def _iou(a, b):
                    ix1 = max(a['x1'], b['x1']); iy1 = max(a['y1'], b['y1'])
                    ix2 = min(a['x2'], b['x2']); iy2 = min(a['y2'], b['y2'])
                    iw = max(0.0, ix2 - ix1); ih = max(0.0, iy2 - iy1)
                    inter = iw * ih
                    area_a = max(0.0, (a['x2']-a['x1'])) * max(0.0, (a['y2']-a['y1']))
                    area_b = max(0.0, (b['x2']-b['x1'])) * max(0.0, (b['y2']-b['y1']))
                    union = area_a + area_b - inter + 1e-6
                    return inter / union
                iou_thresh = float(data.get('iou_thresh', 0.5))
                filtered = []
                for l in boxes:
                    dup = False
                    for e in exist_manual:
                        if e['class'] == l['class'] and _iou(e, l) >= iou_thresh:
                            dup = True; break
                    if not dup:
                        for e in exist_auto:
                            if e['class'] == l['class'] and _iou(e, l) >= iou_thresh:
                                dup = True; break
                    if not dup:
                        filtered.append(l)
                if not filtered:
                    continue
                lines = []
                # 读取已有 auto 标签（允许追加）
                if os.path.exists(auto_lbl_path):
                    try:
                        with open(auto_lbl_path, 'r', encoding='utf-8') as f:
                            lines = [ln.strip() for ln in f if ln.strip()]
                    except Exception:
                        lines = []
                # 追加自动标注（标注来源不可见写入，可在旁文件记录）
                for l in filtered:
                    cx = ((l['x1'] + l['x2']) / 2.0) / w
                    cy = ((l['y1'] + l['y2']) / 2.0) / h
                    ww = (l['x2'] - l['x1']) / w
                    hh = (l['y2'] - l['y1']) / h
                    lines.append(f"{l['class']} {cx:.6f} {cy:.6f} {ww:.6f} {hh:.6f}")
                os.makedirs(os.path.dirname(auto_lbl_path), exist_ok=True)
                try:
                    with open(auto_lbl_path, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(lines))
                    added += len(filtered)
                    pending += 1
                except Exception:
                    pass
            batch_status['progress'] = int((i + len(batch)) / total * 100) if total else 100
        batch_status.update({'is_running': False, 'message': '完成'})
        return jsonify({'success': True, 'count': len(images), 'added_boxes': added, 'pending_count': pending})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/auto_annotate/batch/status')
def api_auto_annotate_batch_status():
    global batch_status
    if 'batch_status' not in globals():
        batch_status = {'is_running': False, 'progress': 0, 'message': ''}
    return jsonify({'success': True, 'status': batch_status})

# 待复核列表：含最近自动标注的图片
@app.route('/api/annotation/pending')
def api_annotation_pending():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        split = request.args.get('split', 'train')
        offset = int(request.args.get('offset', '0'))
        limit = int(request.args.get('limit', '50'))
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, 'auto_labels', split)
        items = []
        for root, _, fs in os.walk(img_dir):
            for f in fs:
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    ip = os.path.join(root, f)
                    rel = os.path.relpath(ip, img_dir)
                    lp = os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')
                    if os.path.exists(lp):
                        items.append({'url': f"/api/file?path={ip}", 'path': ip})
        total = len(items)
        page = items[offset:offset+limit]
        return jsonify({'success': True, 'images': page, 'total': total})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 保存标注（转 YOLO 归一化）
@app.route('/api/annotation/save', methods=['POST'])
def api_annotation_save():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        split = data.get('split', 'train')
        image_path = data.get('image_path')
        labels = data.get('labels') or []
        if not project_path or not dataset_name or not image_path:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        # 获取尺寸
        try:
            from PIL import Image
            with Image.open(image_path) as im:
                w, h = im.size
        except Exception:
            return jsonify({'success': False, 'error': '无法读取图片尺寸'})
        # 写入 YOLO 文本
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, split, 'labels')
        auto_dir = os.path.join(ds_root, 'auto_labels', split)
        os.makedirs(lbl_dir, exist_ok=True)
        rel = os.path.relpath(image_path, img_dir)
        rel_noext = os.path.splitext(rel)[0]
        lbl_path = os.path.join(lbl_dir, rel_noext + '.txt')
        auto_path = os.path.join(auto_dir, rel_noext + '.txt')
        lines = []
        for l in labels:
            cls = int(l.get('class', 0))
            x1, y1, x2, y2 = float(l['x1']), float(l['y1']), float(l['x2']), float(l['y2'])
            cx = ((x1 + x2) / 2.0) / w
            cy = ((y1 + y2) / 2.0) / h
            ww = (x2 - x1) / w
            hh = (y2 - y1) / h
            lines.append(f"{cls} {cx:.6f} {cy:.6f} {ww:.6f} {hh:.6f}")
        with open(lbl_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        # 保存后若存在对应 auto_labels，则删除以完成合并效果
        try:
            if os.path.exists(auto_path):
                os.remove(auto_path)
        except Exception:
            pass
        return jsonify({'success': True, 'label_path': lbl_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 读取标签
@app.route('/api/annotation/get')
def api_annotation_get():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        split = request.args.get('split', 'train')
        image_path = request.args.get('image_path')
        if not project_path or not dataset_name or not image_path:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, split, 'labels')
        auto_dir = os.path.join(ds_root, 'auto_labels', split)
        rel = os.path.relpath(image_path, img_dir)
        lbl_path = os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')
        auto_path = os.path.join(auto_dir, os.path.splitext(rel)[0] + '.txt')
        boxes = []
        auto_boxes = []
        from PIL import Image
        with Image.open(image_path) as im:
            w, h = im.size
        if os.path.exists(lbl_path):
            try:
                with open(lbl_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            cls = int(float(parts[0]))
                            cx = float(parts[1]) * w
                            cy = float(parts[2]) * h
                            ww = float(parts[3]) * w
                            hh = float(parts[4]) * h
                            x1 = max(0.0, cx - ww/2)
                            y1 = max(0.0, cy - hh/2)
                            x2 = min(float(w), cx + ww/2)
                            y2 = min(float(h), cy + hh/2)
                            boxes.append({'class': cls, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
            except Exception:
                boxes = []
        if os.path.exists(auto_path):
            try:
                with open(auto_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            cls = int(float(parts[0]))
                            cx = float(parts[1]) * w
                            cy = float(parts[2]) * h
                            ww = float(parts[3]) * w
                            hh = float(parts[4]) * h
                            x1 = max(0.0, cx - ww/2)
                            y1 = max(0.0, cy - hh/2)
                            x2 = min(float(w), cx + ww/2)
                            y2 = min(float(h), cy + hh/2)
                            auto_boxes.append({'class': cls, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
            except Exception:
                auto_boxes = []
        return jsonify({'success': True, 'boxes': boxes, 'auto_boxes': auto_boxes, 'width': w, 'height': h})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 上传图片扩充数据集
@app.route('/api/dataset/upload', methods=['POST'])
def api_dataset_upload():
    try:
        project_path = request.form.get('project_path')
        dataset_name = request.form.get('dataset_name')
        split = request.form.get('split', 'train')
        files = request.files.getlist('files')
        if not project_path or not dataset_name or not files:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        target_dir = os.path.join(project_path, 'training', dataset_name, split, 'images')
        os.makedirs(target_dir, exist_ok=True)
        saved = []
        for f in files:
            fn = os.path.basename(f.filename or '')
            if not fn or (not fn.lower().endswith(('.jpg', '.jpeg', '.png'))):
                continue
            name, ext = os.path.splitext(fn)
            dst = os.path.join(target_dir, fn)
            idx = 1
            while os.path.exists(dst):
                dst = os.path.join(target_dir, f"{name}_{idx}{ext}")
                idx += 1
            f.save(dst)
            saved.append(dst)
        return jsonify({'success': True, 'saved': [f"/api/file?path={p}" for p in saved], 'count': len(saved)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/training/continue', methods=['POST'])
def api_training_continue():
    try:
        data = request.get_json()
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name', 'training')
        use_best = data.get('use_best', False)
        training_config = data.get('training_config', {})
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        result = TrainingManager.start_training_from_artifact(project_path, dataset_name, use_best, training_config)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/training/resume', methods=['POST'])
def api_training_resume():
    try:
        data = request.get_json()
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name', 'training')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        result = TrainingManager.resume_last_run(project_path, dataset_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
@app.route('/api/model/evaluate', methods=['POST'])
def api_model_evaluate():
    try:
        data = request.get_json()
        project_path = data.get('project_path')
        training_id = data.get('training_id')
        split = data.get('split', 'val')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        result = TrainingManager.evaluate_model(project_path, training_id, split)
        # 将本地路径转为可访问URL
        imgs = result.get('images', [])
        result['images'] = [f"/api/file?path={p}" for p in imgs]
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/model/evaluate/start', methods=['POST'])
def api_model_evaluate_start():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        split = data.get('split', 'val')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        result = TrainingManager.start_evaluate_async(project_path, split)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/model/evaluate/status')
def api_model_evaluate_status():
    try:
        st = TrainingManager.get_evaluate_status()
        # 将路径转换为可访问 URL
        imgs = st.get('results', {}).get('images', [])
        st['results']['images'] = [f"/api/file?path={p}" for p in imgs]
        return jsonify({'success': True, 'status': st})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/file')
def api_file():
    try:
        p = request.args.get('path')
        if not p or not os.path.exists(p):
            return jsonify({'success': False, 'error': '文件不存在'})
        return send_file(p)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
@app.route('/api/dataset/validate', methods=['POST'])
def api_validate_dataset():
    """验证数据集"""
    try:
        data = request.get_json()
        dataset_path = data.get('dataset_path')
        
        if not dataset_path or not os.path.exists(dataset_path):
            return jsonify({'success': False, 'error': '数据集路径无效'})
        
        # 分析数据集
        dataset_info = ProjectManager.analyze_dataset(dataset_path)
        if not dataset_info:
            return jsonify({'success': False, 'error': '无法分析数据集'})
        
        # 检查是否可以进行训练
        validation_result = {
            'can_train': dataset_info['annotation_rate'] > 0.8,  # 标注率大于80%才能训练
            'can_validate': dataset_info['has_val'],
            'can_test': dataset_info['has_test'],
            'annotation_rate': dataset_info['annotation_rate'],
            'image_count': dataset_info['image_count'],
            'label_count': dataset_info['label_count']
        }
        
        return jsonify({
            'success': True,
            'validation': validation_result,
            'dataset_info': dataset_info
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

   
@app.route('/api/training/runs')
def api_training_runs():
    try:
        project_path = request.args.get('project_path')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        runs = TrainingManager.list_training_runs(project_path)
        return jsonify({'success': True, 'runs': runs})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/dataset/diagnose')
def api_dataset_diagnose():
    try:
        project_path = request.args.get('project_path')
        training_id = request.args.get('training_id')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        cfg = None
        base = os.path.join(project_path, 'training_outputs')
        if training_id:
            if os.path.exists(base):
                for ds in os.listdir(base):
                    p = os.path.join(base, ds, training_id, 'training_config.json')
                    if os.path.exists(p):
                        cfg = p
                        break
        else:
            _, training_id = TrainingManager.get_latest_run_dir(project_path)
            if training_id and os.path.exists(base):
                for ds in os.listdir(base):
                    p = os.path.join(base, ds, training_id, 'training_config.json')
                    if os.path.exists(p):
                        cfg = p
                        break
        dataset_yaml = None
        if cfg and os.path.exists(cfg):
            try:
                with open(cfg, 'r', encoding='utf-8') as f:
                    j = json.load(f)
                    dataset_yaml = j.get('dataset_yaml')
            except Exception:
                pass
        diag = {'training_id': training_id, 'dataset_yaml': dataset_yaml}
        images_train = None; labels_train = None
        exists_images = False; exists_labels = False
        if dataset_yaml and os.path.exists(dataset_yaml):
            try:
                with open(dataset_yaml, 'r', encoding='utf-8') as f:
                    y = yaml.safe_load(f) or {}
                base_path = y.get('path') or os.path.dirname(dataset_yaml)
                def ap(p):
                    return p if (p and os.path.isabs(p)) else (os.path.join(base_path, p) if p else None)
                images_train = ap(y.get('train')) or os.path.join(base_path, 'images', 'train')
                labels_train = os.path.join(base_path, 'labels', 'train')
                exists_images = bool(images_train and os.path.exists(images_train))
                exists_labels = bool(labels_train and os.path.exists(labels_train))
            except Exception:
                pass
        diag.update({
            'images_train': images_train,
            'labels_train': labels_train,
            'exists_images_train': exists_images,
            'exists_labels_train': exists_labels,
        })
        msg = ''
        if not exists_images:
            msg = '缺少 images/train 目录；请在 dataset.yaml 设置 path 与 train 或创建该目录'
        elif not exists_labels:
            msg = '缺少 labels/train 目录；将按图片均匀采样，不做类别均匀'
        return jsonify({'success': True, 'diagnose': diag, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})



 
# 将已复核的 auto_labels 合并到人工 labels
@app.route('/api/annotation/commit', methods=['POST'])
def api_annotation_commit():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        split = data.get('split', 'train')
        image_path = data.get('image_path')
        if not project_path or not dataset_name or not image_path:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        manual_dir = os.path.join(ds_root, 'labels', split)
        auto_dir = os.path.join(ds_root, 'auto_labels', split)
        os.makedirs(manual_dir, exist_ok=True)
        os.makedirs(auto_dir, exist_ok=True)
        rel = os.path.relpath(image_path, img_dir)
        manual_lbl = os.path.join(manual_dir, os.path.splitext(rel)[0] + '.txt')
        auto_lbl = os.path.join(auto_dir, os.path.splitext(rel)[0] + '.txt')
        lines_manual = []
        lines_auto = []
        if os.path.exists(manual_lbl):
            try:
                with open(manual_lbl, 'r', encoding='utf-8') as f:
                    lines_manual = [ln.strip() for ln in f if ln.strip()]
            except Exception:
                lines_manual = []
        if os.path.exists(auto_lbl):
            try:
                with open(auto_lbl, 'r', encoding='utf-8') as f:
                    lines_auto = [ln.strip() for ln in f if ln.strip()]
            except Exception:
                lines_auto = []
        # 合并策略：人工优先，简单追加 auto 行（复核后提交）
        merged = lines_manual + lines_auto
        with open(manual_lbl, 'w', encoding='utf-8') as f:
            f.write('\n'.join(merged))
        # 提交后删除 auto 文件
        try:
            if os.path.exists(auto_lbl):
                os.remove(auto_lbl)
        except Exception:
            pass
        return jsonify({'success': True, 'label_path': manual_lbl})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/dataset/delete', methods=['POST'])
def api_dataset_delete():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        split = data.get('split', 'train')
        image_rel = data.get('image_rel')
        image_path = data.get('image_path')
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, split, 'labels')
        if not image_rel and image_path:
            key = os.sep + split + os.sep + 'images' + os.sep
            pos = image_path.find(key)
            if pos >= 0:
                image_rel = image_path[pos+len(key):]
            else:
                # 退化为文件名
                image_rel = os.path.basename(image_path)
        if not image_rel:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        img_path = os.path.join(img_dir, image_rel)
        lbl_path = os.path.join(lbl_dir, os.path.splitext(image_rel)[0] + '.txt')
        deleted = {'image': False, 'label': False}
        if os.path.exists(img_path):
            os.remove(img_path)
            deleted['image'] = True
        if os.path.exists(lbl_path):
            os.remove(lbl_path)
            deleted['label'] = True
        return jsonify({'success': True, 'deleted': deleted})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

 
# 批量自动标注进度状态
batch_status = {
    'is_running': False,
    'progress': 0,
    'message': ''
}

 
# 保存自动标注到 auto_labels（转 YOLO 归一化）
@app.route('/api/annotation/save_auto', methods=['POST'])
def api_annotation_save_auto():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        split = data.get('split', 'train')
        image_path = data.get('image_path')
        labels = data.get('labels') or []
        if not project_path or not dataset_name or not image_path:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        try:
            from PIL import Image
            with Image.open(image_path) as im:
                w, h = im.size
        except Exception:
            return jsonify({'success': False, 'error': '无法读取图片尺寸'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        auto_dir = os.path.join(ds_root, 'auto_labels', split)
        os.makedirs(auto_dir, exist_ok=True)
        rel = os.path.relpath(image_path, img_dir)
        lbl_path = os.path.join(auto_dir, os.path.splitext(rel)[0] + '.txt')
        lines = []
        for l in labels:
            cls = int(l.get('class', 0))
            x1, y1, x2, y2 = float(l['x1']), float(l['y1']), float(l['x2']), float(l['y2'])
            cx = ((x1 + x2) / 2.0) / w
            cy = ((y1 + y2) / 2.0) / h
            ww = (x2 - x1) / w
            hh = (y2 - y1) / h
            lines.append(f"{cls} {cx:.6f} {cy:.6f} {ww:.6f} {hh:.6f}")
        with open(lbl_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        return jsonify({'success': True, 'label_path': lbl_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

 

if __name__ == '__main__':
    print("🎯 数据集工具启动中...")
    print("🌐 请在浏览器中打开: http://localhost:5001")
    
    app.run(host='0.0.0.0', port=5001, debug=False)

 