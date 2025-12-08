#!/usr/bin/env python3
"""
增量行为识别训练脚本
支持逐步添加新的行为类别，保持已学习的知识
"""

import os
import yaml
import shutil
from pathlib import Path
from ultralytics import YOLO
import logging
from datetime import datetime

class IncrementalBehaviorTrainer:
    """增量行为识别训练器"""
    
    def __init__(self, base_model_dir=None):
        if base_model_dir is None:
            # 动态获取项目根目录
            project_root = Path(__file__).parent.parent.parent.absolute()
            base_model_dir = project_root / "models" / "layer3_behavior_detection"
        self.base_dir = Path(base_model_dir)
        self.models_dir = self.base_dir / "models"
        self.datasets_dir = self.base_dir / "datasets"
        self.config_dir = self.base_dir / "config"
        
        # 创建目录
        for dir_path in [self.models_dir, self.datasets_dir, self.config_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # 设置日志
        self.setup_logging()
        
        # 行为类别映射
        self.workflow_behaviors = {
            0: "coal_screening",    # 筛煤
            1: "weighing",          # 称重
            2: "recording",         # 记录
            3: "loading",           # 装载
            4: "inspection",        # 检查
        }
        
        self.violation_behaviors = {
            0: "smoking",           # 吸烟
            1: "phone_use",         # 玩手机
            2: "spitting",          # 吐痰
            3: "sleeping",          # 睡觉
            4: "fighting",          # 打架
        }
        
        self.current_classes = []
        
        # 检查GPU可用性
        self.device = self._check_gpu_availability()
    
    def _check_gpu_availability(self):
        """检查GPU可用性并返回最优设备"""
        try:
            import torch
            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                self.logger.info(f"检测到 {gpu_count} 个GPU")
                for i in range(gpu_count):
                    gpu_name = torch.cuda.get_device_name(i)
                    gpu_memory = torch.cuda.get_device_properties(i).total_memory / 1024**3
                    self.logger.info(f"  GPU {i}: {gpu_name} ({gpu_memory:.1f}GB)")
                
                # 选择显存最多的GPU
                if gpu_count > 1:
                    max_memory = 0
                    best_gpu = 0
                    for i in range(gpu_count):
                        memory = torch.cuda.get_device_properties(i).total_memory
                        if memory > max_memory:
                            max_memory = memory
                            best_gpu = i
                    return str(best_gpu)
                else:
                    return '0'
            else:
                self.logger.info("GPU不可用，使用CPU训练")
                return 'cpu'
        except ImportError:
            self.logger.warning("PyTorch未安装，使用CPU训练")
            return 'cpu'
        except Exception as e:
            self.logger.warning(f"检查GPU可用性失败: {e}，使用CPU训练")
            return 'cpu'
    
    def setup_logging(self):
        """设置日志"""
        log_file = self.base_dir / f"incremental_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def create_dataset_config(self, behavior_name, dataset_path, existing_classes=None):
        """创建数据集配置文件"""
        if existing_classes is None:
            existing_classes = []
        
        # 更新类别列表
        if behavior_name not in existing_classes:
            existing_classes.append(behavior_name)
        
        config = {
            'path': str(dataset_path),
            'train': 'train',
            'val': 'val',
            'test': 'test',
            'nc': len(existing_classes),
            'names': {i: name for i, name in enumerate(existing_classes)}
        }
        
        config_file = self.config_dir / f"behavior_dataset_{len(existing_classes)}classes.yaml"
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        self.logger.info(f"创建数据集配置: {config_file}")
        self.logger.info(f"类别: {existing_classes}")
        
        return config_file, existing_classes
    
    def prepare_incremental_dataset(self, new_behavior_data, behavior_name, existing_dataset=None):
        """准备增量训练数据集"""
        self.logger.info(f"准备增量数据集 - 新行为: {behavior_name}")
        
        # 创建新的数据集目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dataset_name = f"behavior_dataset_{timestamp}"
        dataset_path = self.datasets_dir / dataset_name
        
        # 创建标准YOLO目录结构
        for split in ['train', 'val', 'test']:
            (dataset_path / split / 'images').mkdir(parents=True, exist_ok=True)
            (dataset_path / split / 'labels').mkdir(parents=True, exist_ok=True)
        
        # 如果有现有数据集，先复制过来
        existing_classes = []
        if existing_dataset and existing_dataset.exists():
            self.logger.info(f"复制现有数据集: {existing_dataset}")
            # 这里需要实现数据集合并逻辑
            # 复制现有的图像和标签，更新类别索引
            existing_classes = self.get_existing_classes(existing_dataset)
        
        # 添加新行为数据
        self.add_new_behavior_data(dataset_path, new_behavior_data, behavior_name, existing_classes)
        
        # 创建配置文件
        config_file, all_classes = self.create_dataset_config(behavior_name, dataset_path, existing_classes)
        
        return dataset_path, config_file, all_classes
    
    def get_existing_classes(self, dataset_path):
        """获取现有数据集的类别"""
        config_files = list(self.config_dir.glob("behavior_dataset_*classes.yaml"))
        if config_files:
            latest_config = max(config_files, key=os.path.getctime)
            with open(latest_config, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return list(config['names'].values())
        return []
    
    def add_new_behavior_data(self, dataset_path, new_data_path, behavior_name, existing_classes):
        """添加新行为数据到数据集"""
        self.logger.info(f"添加新行为数据: {behavior_name}")
        
        new_class_id = len(existing_classes)
        
        # 这里需要实现具体的数据添加逻辑
        # 包括图像复制和标签文件创建/更新
        # 暂时提供框架代码
        
        self.logger.info(f"新行为 '{behavior_name}' 分配类别ID: {new_class_id}")
    
    def train_incremental_model(self, config_file, previous_model=None, epochs=100):
        """增量训练模型"""
        self.logger.info("开始增量训练...")
        
        # 选择基础模型
        if previous_model and Path(previous_model).exists():
            self.logger.info(f"基于现有模型继续训练: {previous_model}")
            model = YOLO(previous_model)
        else:
            self.logger.info("从预训练模型开始训练")
            model = YOLO('yolov8n.pt')  # 或使用其他预训练模型
        
        # 根据设备调整训练参数
        batch_size = 32 if self.device != 'cpu' else 8
        workers = 8 if self.device != 'cpu' else 4
        
        # 训练参数
        train_args = {
            'data': str(config_file),
            'epochs': epochs,
            'imgsz': 640,
            'batch': batch_size,
            'lr0': 0.001,  # 较小的学习率用于增量训练
            'patience': 20,
            'save_period': 10,
            'device': self.device,
            'workers': workers,
            'project': str(self.models_dir),
            'name': f'incremental_behavior_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'exist_ok': True
        }
        
        # GPU优化参数
        if self.device != 'cpu':
            train_args.update({
                'amp': True,  # 自动混合精度
                'cache': True,  # 缓存数据集
                'close_mosaic': 10,  # 最后10个epoch关闭mosaic增强
            })
        
        self.logger.info(f"训练设备: {self.device}")
        self.logger.info(f"批次大小: {batch_size}")
        self.logger.info(f"工作线程: {workers}")
        self.logger.info(f"AMP混合精度: {self.device != 'cpu'}")
        
        # 开始训练
        results = model.train(**train_args)
        
        # 保存最佳模型
        best_model_path = self.models_dir / f"behavior_model_incremental_{len(self.current_classes)}classes.pt"
        shutil.copy(results.save_dir / 'weights' / 'best.pt', best_model_path)
        
        self.logger.info(f"增量训练完成，最佳模型保存至: {best_model_path}")
        
        return best_model_path, results
    
    def validate_incremental_model(self, model_path, config_file):
        """验证增量训练的模型"""
        self.logger.info("验证增量训练模型...")
        
        model = YOLO(model_path)
        results = model.val(data=str(config_file))
        
        self.logger.info("验证结果:")
        self.logger.info(f"mAP50: {results.box.map50:.4f}")
        self.logger.info(f"mAP50-95: {results.box.map:.4f}")
        
        return results


def main():
    """主函数 - 演示增量训练流程"""
    print("="*60)
    print("增量行为识别训练指南")
    print("="*60)
    
    trainer = IncrementalBehaviorTrainer()
    
    print("\n推荐的增量训练流程:")
    print("1. 第一阶段：训练抽烟检测")
    print("   - 准备抽烟行为数据集")
    print("   - 从预训练YOLO模型开始训练")
    print("   - 保存抽烟检测模型")
    
    print("\n2. 第二阶段：增加玩手机检测")
    print("   - 准备玩手机行为数据集")
    print("   - 基于抽烟检测模型继续训练")
    print("   - 模型现在可以识别两种行为")
    
    print("\n3. 未来阶段：继续添加其他行为")
    print("   - 睡觉、打架等其他行为")
    print("   - 每次都基于前一个模型训练")
    
    print("\n关键要点:")
    print("✅ 使用较小的学习率 (如0.001)")
    print("✅ 保持数据集平衡")
    print("✅ 定期验证所有类别的性能")
    print("✅ 保存每个阶段的模型备份")
    
    print("\n数据集组织建议:")
    print("behavior_datasets/")
    print("├── smoking/")
    print("│   ├── train/")
    print("│   ├── val/")
    print("│   └── test/")
    print("├── phone_use/")
    print("│   ├── train/")
    print("│   ├── val/")
    print("│   └── test/")
    print("└── combined/")
    print("    ├── train/  # 包含所有行为")
    print("    ├── val/")
    print("    └── test/")
    
    print("\n使用示例:")
    print("# 第一阶段训练")
    print("python train_behavior_yolo.py --data smoking_dataset.yaml --epochs 100")
    print("\n# 第二阶段增量训练")
    print("python train_behavior_yolo.py --data combined_dataset.yaml --weights smoking_model.pt --epochs 50")


if __name__ == "__main__":
    main()