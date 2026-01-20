import os
import sys
import json
import yaml
import shutil
import time
import threading
import queue
import logging
from datetime import datetime
from collections import deque

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import PROJECT_ROOT, get_device

# 全局状态
training_status = {
    'is_running': False,
    'epoch': 0,
    'epochs': 100,
    'box_loss': 0,
    'cls_loss': 0,
    'dfl_loss': 0,
    'map50': 0,
    'map50_95': 0,
    'gpu_mem': 0,
    'instances': 0,
    'progress': 0,
    'message': '',
    'error': None,
    'stop_requested': False,
    'log': deque(maxlen=1000)
}

eval_status = {
    'is_running': False,
    'progress': 0,
    'message': '',
    'results': None,
    'error': None
}

class TrainingManager:
    """训练任务管理器"""
    @staticmethod
    def start_training(project_path, dataset_name, model_name, training_config, dataset_path=None):
        """启动训练任务"""
        if training_status['is_running']:
            return {'success': False, 'error': '已有训练任务正在运行'}
            
        # 重置状态
        training_status.update({
            'is_running': True,
            'epoch': 0,
            'epochs': int(training_config.get('epochs', 100)),
            'box_loss': 0,
            'cls_loss': 0,
            'dfl_loss': 0,
            'map50': 0,
            'map50_95': 0,
            'progress': 0,
            'message': '初始化训练...',
            'error': None,
            'stop_requested': False
        })
        training_status['log'].clear()
        
        # 异步启动
        def run_train():
            try:
                # 准备目录
                train_id = datetime.now().strftime('%Y%m%d_%H%M%S')
                save_dir = os.path.join(project_path, "training_outputs", dataset_name, train_id)
                os.makedirs(save_dir, exist_ok=True)
                
                # 保存配置
                config_save = {
                    'dataset_name': dataset_name,
                    'model_name': model_name,
                    'config': training_config,
                    'dataset_path': dataset_path,
                    'start_time': train_id
                }
                with open(os.path.join(save_dir, 'training_config.json'), 'w') as f:
                    json.dump(config_save, f, indent=2)

                # 准备 data.yaml
                if not dataset_path:
                    # 默认路径
                    dataset_path = os.path.join(project_path, "training", dataset_name)
                    
                data_yaml = os.path.join(dataset_path, "data.yaml")
                if not os.path.exists(data_yaml):
                    # 尝试自动生成
                    TrainingManager.generate_data_yaml(dataset_path, save_dir)
                    data_yaml = os.path.join(save_dir, "data.yaml")
                    
                # 记录使用的 dataset.yaml
                config_save['dataset_yaml'] = data_yaml
                with open(os.path.join(save_dir, 'training_config.json'), 'w') as f:
                    json.dump(config_save, f, indent=2)

                training_status['message'] = f'开始训练 {model_name}...'
                training_status['log'].append(f"训练输出目录: {save_dir}")
                
                # 调用 YOLO
                from ultralytics import YOLO
                model = YOLO(model_name)
                
                # 自定义回调更新状态
                def on_train_epoch_end(trainer):
                    if training_status['stop_requested']:
                        trainer.stop = True
                        raise InterruptedError("用户终止训练")
                        
                    metrics = trainer.metrics
                    training_status['epoch'] = trainer.epoch + 1
                    training_status['epochs'] = trainer.epochs
                    training_status['box_loss'] = float(trainer.loss_items[0]) if len(trainer.loss_items)>0 else 0
                    training_status['cls_loss'] = float(trainer.loss_items[1]) if len(trainer.loss_items)>1 else 0
                    training_status['dfl_loss'] = float(trainer.loss_items[2]) if len(trainer.loss_items)>2 else 0
                    training_status['map50'] = float(metrics.get('metrics/mAP50(B)', 0))
                    training_status['map50_95'] = float(metrics.get('metrics/mAP50-95(B)', 0))
                    training_status['progress'] = int((trainer.epoch + 1) / trainer.epochs * 100)
                    
                    # 记录日志
                    msg = f"Epoch {trainer.epoch+1}/{trainer.epochs} box_loss:{training_status['box_loss']:.4f} mAP50:{training_status['map50']:.4f}"
                    training_status['log'].append(msg)

                model.add_callback("on_train_epoch_end", on_train_epoch_end)
                
                # 训练参数
                args = {
                    'data': data_yaml,
                    'epochs': int(training_config.get('epochs', 100)),
                    'imgsz': int(training_config.get('imgsz', 640)),
                    'batch': int(training_config.get('batch', 16)),
                    'device': get_device(),
                    'project': os.path.dirname(save_dir),
                    'name': os.path.basename(save_dir),
                    'exist_ok': True,
                    'patience': 50,
                    'save': True
                }
                
                model.train(**args)
                
                training_status['message'] = '训练完成'
                training_status['progress'] = 100
                training_status['log'].append("训练成功完成")
                
            except InterruptedError:
                training_status['message'] = '训练已终止'
                training_status['log'].append("用户手动停止训练")
            except Exception as e:
                import traceback
                err = traceback.format_exc()
                training_status['error'] = str(e)
                training_status['message'] = '训练出错'
                training_status['log'].append(f"错误: {str(e)}\n{err}")
            finally:
                training_status['is_running'] = False

        thread = threading.Thread(target=run_train)
        thread.daemon = True
        thread.start()
        
        return {'success': True, 'message': '训练任务已启动'}

    @staticmethod
    def stop_training():
        """停止训练"""
        if training_status['is_running']:
            training_status['stop_requested'] = True
            return {'success': True, 'message': '正在停止训练...'}
        return {'success': False, 'error': '没有正在运行的训练任务'}

    @staticmethod
    def generate_data_yaml(dataset_path, save_dir):
        """生成 data.yaml"""
        # 简单的自动生成逻辑
        yaml_content = {
            'path': dataset_path,
            'train': 'train/images',
            'val': 'val/images',
            'test': 'test/images',  # optional
            'names': {}
        }
        
        # 尝试读取 classes.txt 或分析 labels
        # 这里简化处理，扫描 labels 目录获取最大 class id
        classes = set()
        for split in ['train', 'val']:
            lbl_dir = os.path.join(dataset_path, split, 'labels')
            if os.path.exists(lbl_dir):
                for f in os.listdir(lbl_dir):
                    if f.endswith('.txt'):
                        try:
                            with open(os.path.join(lbl_dir, f), 'r') as lf:
                                for line in lf:
                                    c = int(line.split()[0])
                                    classes.add(c)
                        except:
                            pass
                            
        # 生成 names map
        max_id = max(classes) if classes else 0
        names = {i: f"class_{i}" for i in range(max_id + 1)}
        yaml_content['names'] = names
        
        with open(os.path.join(save_dir, 'data.yaml'), 'w') as f:
            yaml.dump(yaml_content, f)

    @staticmethod
    def list_training_runs(project_path):
        """列出所有训练记录"""
        runs = []
        base = os.path.join(project_path, "training_outputs")
        if not os.path.exists(base):
            return runs
            
        for dataset_name in os.listdir(base):
            ds_dir = os.path.join(base, dataset_name)
            if not os.path.isdir(ds_dir):
                continue
                
            for run_id in os.listdir(ds_dir):
                run_dir = os.path.join(ds_dir, run_id)
                if not os.path.isdir(run_dir):
                    continue
                    
                # 读取 config
                cfg_path = os.path.join(run_dir, 'training_config.json')
                config = {}
                if os.path.exists(cfg_path):
                    try:
                        with open(cfg_path, 'r') as f:
                            config = json.load(f)
                    except:
                        pass
                        
                # 检查是否有结果
                results_csv = os.path.join(run_dir, 'results.csv')
                status = 'completed' if os.path.exists(os.path.join(run_dir, 'weights', 'best.pt')) else 'running/failed'
                
                runs.append({
                    'id': run_id,
                    'dataset': dataset_name,
                    'path': run_dir,
                    'config': config,
                    'status': status,
                    'created_at': datetime.fromtimestamp(os.path.getctime(run_dir)).strftime('%Y-%m-%d %H:%M:%S')
                })
                
        return sorted(runs, key=lambda x: x['id'], reverse=True)

    @staticmethod
    def get_latest_artifacts(project_path):
        """获取最新训练产物"""
        # 简单实现：查找最近修改的 weights 目录
        runs = TrainingManager.list_training_runs(project_path)
        if not runs:
            return {}
            
        latest = runs[0]
        run_dir = latest['path']
        weights_dir = os.path.join(run_dir, 'weights')
        
        artifacts = {
            'run_id': latest['id'],
            'dataset': latest['dataset'],
            'weights_best': os.path.join(weights_dir, 'best.pt') if os.path.exists(os.path.join(weights_dir, 'best.pt')) else None,
            'weights_last': os.path.join(weights_dir, 'last.pt') if os.path.exists(os.path.join(weights_dir, 'last.pt')) else None,
            'results_csv': os.path.join(run_dir, 'results.csv'),
            'confusion_matrix': os.path.join(run_dir, 'confusion_matrix.png')
        }
        return artifacts

    @staticmethod
    def start_training_from_artifact(project_path, dataset_name, use_best, training_config):
        """从已有产物继续训练 (Finetune)"""
        arts = TrainingManager.get_latest_artifacts(project_path)
        weights = arts.get('weights_best') if use_best else arts.get('weights_last')
        
        if not weights or not os.path.exists(weights):
            return {'success': False, 'error': '未找到可用权重文件'}
            
        return TrainingManager.start_training(
            project_path, 
            dataset_name, 
            weights, # 使用权重路径作为 model_name
            training_config
        )

    @staticmethod
    def resume_last_run(project_path, dataset_name):
        """恢复中断的训练"""
        # 找到最近的 last.pt
        runs = TrainingManager.list_training_runs(project_path)
        target_run = None
        for r in runs:
            if r['dataset'] == dataset_name:
                target_run = r
                break
        
        if not target_run:
            return {'success': False, 'error': '未找到该数据集的训练记录'}
            
        last_pt = os.path.join(target_run['path'], 'weights', 'last.pt')
        if not os.path.exists(last_pt):
            return {'success': False, 'error': '未找到断点文件 (last.pt)'}
            
        # 启动恢复
        if training_status['is_running']:
            return {'success': False, 'error': '已有训练任务正在运行'}

        training_status.update({
            'is_running': True,
            'message': '恢复训练中...',
            'error': None,
            'stop_requested': False
        })
        
        def run_resume():
            try:
                from ultralytics import YOLO
                model = YOLO(last_pt)
                model.train(resume=True)
                training_status['message'] = '训练完成'
                training_status['is_running'] = False
            except Exception as e:
                training_status['error'] = str(e)
                training_status['is_running'] = False
                
        thread = threading.Thread(target=run_resume)
        thread.daemon = True
        thread.start()
        
        return {'success': True, 'message': '训练已恢复'}

    @staticmethod
    def evaluate_model(project_path, training_id, split='val'):
        """评估模型"""
        # 查找 run path
        runs = TrainingManager.list_training_runs(project_path)
        run = next((r for r in runs if r['id'] == training_id), None)
        if not run:
            raise ValueError("未找到指定训练记录")
            
        weights = os.path.join(run['path'], 'weights', 'best.pt')
        if not os.path.exists(weights):
            weights = os.path.join(run['path'], 'weights', 'last.pt')
            
        if not os.path.exists(weights):
            raise ValueError("未找到权重文件")
            
        from ultralytics import YOLO
        model = YOLO(weights)
        
        # 读取 data.yaml
        data_yaml = None
        if run['config'].get('dataset_yaml'):
            data_yaml = run['config']['dataset_yaml']
        else:
            # 尝试推断
             data_yaml = os.path.join(run['path'], 'data.yaml')
             
        if not data_yaml or not os.path.exists(data_yaml):
             raise ValueError("未找到数据集配置文件")
             
        metrics = model.val(data=data_yaml, split=split)
        
        # 返回评估结果
        return {
            'map50': metrics.box.map50,
            'map50_95': metrics.box.map,
            'precision': metrics.box.mp,
            'recall': metrics.box.mr,
            'images': [] # TODO: 获取评估生成的图片
        }

    @staticmethod
    def start_evaluate_async(project_path, split='val'):
        """异步评估"""
        if eval_status['is_running']:
             return {'success': False, 'error': '已有评估任务正在运行'}
             
        eval_status.update({
            'is_running': True,
            'progress': 0,
            'message': '开始评估...',
            'results': None,
            'error': None
        })
        
        def run_eval():
            try:
                # 获取最新的训练 run
                arts = TrainingManager.get_latest_artifacts(project_path)
                if not arts.get('weights_best'):
                    raise ValueError("无可用模型权重")
                    
                res = TrainingManager.evaluate_model(project_path, arts['run_id'], split)
                eval_status['results'] = res
                eval_status['message'] = '评估完成'
            except Exception as e:
                eval_status['error'] = str(e)
                eval_status['message'] = '评估失败'
            finally:
                eval_status['is_running'] = False
                
        thread = threading.Thread(target=run_eval)
        thread.daemon = True
        thread.start()
        return {'success': True, 'message': '评估任务已启动'}

    @staticmethod
    def get_evaluate_status():
        return eval_status
    
    @staticmethod
    def get_latest_run_dir(project_path):
        """获取最新的 run 目录和 id"""
        runs = TrainingManager.list_training_runs(project_path)
        if runs:
            return runs[0]['path'], runs[0]['id']
        return None, None
