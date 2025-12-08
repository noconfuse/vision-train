#!/usr/bin/env python3
"""
火焰检测模型验证脚本
评估训练完成的模型性能
"""

import os
import argparse
from pathlib import Path
import cv2
import numpy as np
from ultralytics import YOLO
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report
import json

def load_model(model_path):
    """加载训练好的模型"""
    try:
        model = YOLO(model_path)
        print(f"✅ 模型加载成功: {model_path}")
        return model
    except Exception as e:
        print(f"❌ 模型加载失败: {e}")
        return None

def validate_on_dataset(model, dataset_path, conf_threshold=0.25):
    """在验证集上评估模型"""
    print(f"🔍 在验证集上评估模型...")
    print(f"📁 数据集路径: {dataset_path}")
    print(f"🎯 置信度阈值: {conf_threshold}")
    
    try:
        # 使用YOLO内置的验证功能
        results = model.val(
            data=dataset_path,
            conf=conf_threshold,
            verbose=True
        )
        
        print("📊 验证结果:")
        print(f"  mAP@0.5: {results.box.map50:.4f}")
        print(f"  mAP@0.5:0.95: {results.box.map:.4f}")
        print(f"  Precision: {results.box.mp:.4f}")
        print(f"  Recall: {results.box.mr:.4f}")
        
        return results
        
    except Exception as e:
        print(f"❌ 验证过程出错: {e}")
        return None

def test_on_sample_images(model, image_dir, output_dir, conf_threshold=0.25):
    """在样本图像上测试模型"""
    image_dir = Path(image_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🖼️ 在样本图像上测试模型...")
    print(f"📁 图像目录: {image_dir}")
    print(f"💾 输出目录: {output_dir}")
    
    # 支持的图像格式
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
    image_files = []
    for ext in image_extensions:
        image_files.extend(list(image_dir.glob(f"*{ext}")))
        image_files.extend(list(image_dir.glob(f"*{ext.upper()}")))
    
    if not image_files:
        print("⚠️ 未找到图像文件")
        return
    
    # 随机选择一些图像进行测试
    test_images = image_files[:min(10, len(image_files))]
    
    detection_results = []
    
    for img_path in test_images:
        try:
            # 进行预测
            results = model(str(img_path), conf=conf_threshold)
            
            # 读取原图
            img = cv2.imread(str(img_path))
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # 绘制检测结果
            annotated_img = results[0].plot()
            
            # 保存结果
            output_path = output_dir / f"detected_{img_path.name}"
            cv2.imwrite(str(output_path), annotated_img)
            
            # 记录检测结果
            detections = []
            if results[0].boxes is not None:
                for box in results[0].boxes:
                    detections.append({
                        'confidence': float(box.conf),
                        'class': int(box.cls),
                        'bbox': box.xyxy.tolist()[0]
                    })
            
            detection_results.append({
                'image': img_path.name,
                'detections': detections,
                'detection_count': len(detections)
            })
            
            print(f"  ✅ {img_path.name}: 检测到 {len(detections)} 个火焰")
            
        except Exception as e:
            print(f"  ❌ {img_path.name}: 处理失败 - {e}")
    
    # 保存检测结果统计
    stats_file = output_dir / "detection_stats.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(detection_results, f, indent=2, ensure_ascii=False)
    
    print(f"📊 检测统计已保存: {stats_file}")
    
    return detection_results

def generate_performance_report(model, dataset_path, output_dir):
    """生成性能报告"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("📋 生成性能报告...")
    
    # 验证模型
    val_results = validate_on_dataset(model, dataset_path)
    
    if val_results is None:
        return
    
    # 创建报告
    report = {
        'model_info': {
            'model_type': 'YOLOv11n',
            'task': 'Fire Detection',
            'classes': ['fire']
        },
        'performance_metrics': {
            'mAP_50': float(val_results.box.map50),
            'mAP_50_95': float(val_results.box.map),
            'precision': float(val_results.box.mp),
            'recall': float(val_results.box.mr),
            'f1_score': 2 * (val_results.box.mp * val_results.box.mr) / (val_results.box.mp + val_results.box.mr)
        }
    }
    
    # 保存报告
    report_file = output_dir / "performance_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"📊 性能报告已保存: {report_file}")
    
    # 打印报告摘要
    print("\n📈 性能报告摘要:")
    print(f"  🎯 mAP@0.5: {report['performance_metrics']['mAP_50']:.4f}")
    print(f"  🎯 mAP@0.5:0.95: {report['performance_metrics']['mAP_50_95']:.4f}")
    print(f"  🎯 精确率: {report['performance_metrics']['precision']:.4f}")
    print(f"  🎯 召回率: {report['performance_metrics']['recall']:.4f}")
    print(f"  🎯 F1分数: {report['performance_metrics']['f1_score']:.4f}")
    
    return report

def main():
    parser = argparse.ArgumentParser(description='验证火焰检测模型')
    parser.add_argument('--model', type=str, required=True, help='模型权重文件路径')
    parser.add_argument('--dataset', type=str, help='数据集配置文件路径')
    parser.add_argument('--test-images', type=str, help='测试图像目录')
    parser.add_argument('--output', type=str, default='validation_results', help='输出目录')
    parser.add_argument('--conf', type=float, default=0.25, help='置信度阈值')
    
    args = parser.parse_args()
    
    # 设置路径
    project_root = Path(__file__).parent.parent
    output_dir = project_root / args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("🔥 火焰检测模型验证开始")
    print(f"🤖 模型: {args.model}")
    print(f"📁 输出目录: {output_dir}")
    
    # 加载模型
    model = load_model(args.model)
    if model is None:
        return
    
    # 验证数据集
    if args.dataset:
        print("\n📊 数据集验证:")
        generate_performance_report(model, args.dataset, output_dir)
    
    # 测试样本图像
    if args.test_images:
        print("\n🖼️ 样本图像测试:")
        test_results = test_on_sample_images(
            model, args.test_images, output_dir / "sample_detections", args.conf
        )
    
    print("\n✅ 验证完成!")
    print(f"📁 所有结果保存在: {output_dir}")

if __name__ == "__main__":
    main()