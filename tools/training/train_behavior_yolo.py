#!/usr/bin/env python3
"""
YOLO11行为分类模型训练脚本
"""

import sys
import os
import argparse
from pathlib import Path

# 动态添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.absolute()
sys.path.append(str(project_root / 'src'))

from core.behavior_classifier import YOLOBehaviorRecognizer

def check_gpu_availability():
    """检查GPU可用性"""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            print(f"检测到 {gpu_count} 个GPU:")
            for i in range(gpu_count):
                gpu_name = torch.cuda.get_device_name(i)
                gpu_memory = torch.cuda.get_device_properties(i).total_memory / 1024**3
                print(f"  GPU {i}: {gpu_name} ({gpu_memory:.1f}GB)")
            return True
        else:
            print("未检测到可用的GPU，将使用CPU训练")
            return False
    except ImportError:
        print("PyTorch未安装，无法检查GPU状态")
        return False

def main():
    parser = argparse.ArgumentParser(description='YOLO11行为分类模型训练')
    parser.add_argument('--epochs', type=int, default=100, help='训练轮数')
    parser.add_argument('--batch-size', type=int, default=16, help='批次大小')
    parser.add_argument('--imgsz', type=int, default=640, help='图像尺寸')
    parser.add_argument('--device', type=str, default='auto', help='训练设备 (auto, cpu, 0, 1, ...)')
    parser.add_argument('--workers', type=int, default=8, help='数据加载工作线程数')
    
    args = parser.parse_args()
    
    print("开始训练YOLO11行为分类模型...")
    
    # 检查GPU可用性
    gpu_available = check_gpu_availability()
    
    # 根据GPU可用性调整批次大小
    if gpu_available and args.batch_size == 16:
        # GPU可用时可以使用更大的批次
        args.batch_size = 32
        print(f"GPU可用，调整批次大小为: {args.batch_size}")
    elif not gpu_available and args.batch_size > 8:
        # CPU训练时使用较小批次
        args.batch_size = 8
        print(f"使用CPU训练，调整批次大小为: {args.batch_size}")
    
    # 创建识别器
    recognizer = YOLOBehaviorRecognizer(model_path='yolo11m.pt')
    
    # 开始训练
    results = recognizer.train_behavior_model(
        epochs=args.epochs,
        batch_size=args.batch_size,
        imgsz=args.imgsz,
        device=args.device,
        workers=args.workers
    )
    
    print("训练完成！")
    print(f"最佳模型保存在: {results.save_dir}")

if __name__ == "__main__":
    main()
