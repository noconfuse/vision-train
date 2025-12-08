#!/usr/bin/env python3
"""
火焰检测模型训练脚本 - YOLOv11m版本
使用更大的模型以获得更好的检测精度
"""

import os
import sys
import argparse
from pathlib import Path
from ultralytics import YOLO
import torch

def main():
    parser = argparse.ArgumentParser(description='训练火焰检测模型 - YOLOv11m')
    parser.add_argument('--epochs', type=int, default=100, help='训练轮数')
    parser.add_argument('--batch-size', type=int, default=8, help='批次大小')
    parser.add_argument('--imgsz', type=int, default=640, help='图像尺寸')
    parser.add_argument('--device', type=str, default='0', help='设备 (0 for GPU, cpu for CPU)')
    parser.add_argument('--patience', type=int, default=50, help='早停耐心值')
    parser.add_argument('--save-period', type=int, default=10, help='保存周期')
    parser.add_argument('--resume', type=str, default='', help='恢复训练的权重路径')
    
    args = parser.parse_args()
    
    # 设置路径
    project_root = Path(__file__).parent.parent.parent.absolute()
    dataset_config = project_root / "models/layer1_base_detection/config/fire_dataset.yaml"
    output_dir = project_root / "models/layer1_base_detection/outputs/fire_training_m"
    
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("🔥 火焰检测模型训练开始 (YOLOv11m)")
    print(f"📊 数据集配置: {dataset_config}")
    print(f"📁 输出目录: {output_dir}")
    print(f"🔧 训练参数: epochs={args.epochs}, batch_size={args.batch_size}, imgsz={args.imgsz}")
    
    # 检查GPU可用性和内存
    if torch.cuda.is_available():
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"🚀 使用GPU: {torch.cuda.get_device_name(0)}")
        print(f"💾 GPU内存: {gpu_memory:.1f}GB")
        
        # 根据GPU内存调整批次大小
        if gpu_memory < 8:
            print("⚠️ GPU内存较小，建议减小批次大小")
            if args.batch_size > 4:
                args.batch_size = 4
                print(f"🔧 自动调整批次大小为: {args.batch_size}")
    else:
        print("⚠️ 使用CPU训练 (强烈建议使用GPU)")
        args.device = 'cpu'
        if args.batch_size > 2:
            args.batch_size = 2
            print(f"🔧 CPU模式，调整批次大小为: {args.batch_size}")
    
    # 加载模型
    if args.resume:
        print(f"🔄 从检查点恢复训练: {args.resume}")
        model = YOLO(args.resume)
    else:
        print("🆕 从YOLOv11m预训练模型开始训练")
        model = YOLO('yolo11m.pt')  # 使用YOLOv11 medium预训练模型
    
    # 开始训练
    try:
        results = model.train(
            data=str(dataset_config),
            epochs=args.epochs,
            batch=args.batch_size,
            imgsz=args.imgsz,
            device=args.device,
            patience=args.patience,
            save_period=args.save_period,
            project=str(output_dir),
            name='fire_detection_m_run',
            exist_ok=True,
            verbose=True,
            # 针对复杂检测任务的优化参数
            lr0=0.01,
            momentum=0.937,
            weight_decay=0.0005,
            warmup_epochs=5,  # 增加预热轮数
            warmup_momentum=0.8,
            warmup_bias_lr=0.1,
            # 更保守的数据增强（保持火焰特征）
            hsv_h=0.01,      # 减少色调变化
            hsv_s=0.5,       # 适度饱和度变化
            hsv_v=0.3,       # 适度亮度变化
            degrees=5.0,     # 小角度旋转
            translate=0.1,
            scale=0.3,       # 减少缩放变化
            shear=0.0,       # 不使用剪切
            perspective=0.0, # 不使用透视变换
            flipud=0.0,      # 火焰通常不上下翻转
            fliplr=0.3,      # 适度左右翻转
            mosaic=0.8,      # 适度使用mosaic
            mixup=0.1,       # 少量mixup
            # 损失函数权重调整
            box=7.5,         # 增加边界框损失权重
            cls=0.5,         # 分类损失权重
            dfl=1.5,         # DFL损失权重
        )
        
        print("✅ 训练完成!")
        print(f"📈 最佳模型保存在: {results.save_dir}")
        
        # 显示训练结果摘要
        if hasattr(results, 'results_dict'):
            print("\n📊 训练结果摘要:")
            for key, value in results.results_dict.items():
                if isinstance(value, (int, float)):
                    print(f"  {key}: {value:.4f}")
        
        # 模型性能对比建议
        print("\n🔍 模型性能分析:")
        print("  YOLOv11m相比YOLOv11n的优势:")
        print("  ✅ 更强的特征提取能力")
        print("  ✅ 更好的小目标检测")
        print("  ✅ 更高的检测精度")
        print("  ✅ 更适合复杂场景")
        print("  ⚠️ 推理速度稍慢")
        print("  ⚠️ 模型文件更大")
        
    except Exception as e:
        print(f"❌ 训练过程中出现错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()