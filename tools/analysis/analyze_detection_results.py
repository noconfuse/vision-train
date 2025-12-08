#!/usr/bin/env python3
"""
分析YOLO预训练模型检测结果
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import cv2

def analyze_detection_results(stats_file):
    """分析检测结果统计"""
    
    with open(stats_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("=== YOLO预训练模型检测结果分析 ===\n")
    
    # 基本统计
    total_images = data['total_images']
    images_with_person = data['images_with_person']
    images_with_fire = data['images_with_fire']
    total_persons = data['total_persons']
    total_fires = data['total_fires']
    
    print(f"总图片数: {total_images}")
    print(f"检测到人的图片数: {images_with_person} ({images_with_person/total_images*100:.1f}%)")
    print(f"检测到火的图片数: {images_with_fire} ({images_with_fire/total_images*100:.1f}%)")
    print(f"总人数: {total_persons}")
    print(f"总火源数: {total_fires}")
    print(f"平均每张图片人数: {total_persons/total_images:.2f}")
    
    # 分析人员检测置信度
    person_confidences = []
    person_counts_per_image = []
    
    for result in data['results']:
        person_count = result['person_count']
        person_counts_per_image.append(person_count)
        
        for detection in result['detections']:
            if detection['class_name'] == 'person':
                person_confidences.append(detection['confidence'])
    
    if person_confidences:
        print(f"\n=== 人员检测置信度分析 ===")
        print(f"平均置信度: {np.mean(person_confidences):.3f}")
        print(f"最高置信度: {np.max(person_confidences):.3f}")
        print(f"最低置信度: {np.min(person_confidences):.3f}")
        print(f"置信度标准差: {np.std(person_confidences):.3f}")
        
        # 置信度分布
        high_conf = sum(1 for c in person_confidences if c >= 0.8)
        medium_conf = sum(1 for c in person_confidences if 0.5 <= c < 0.8)
        low_conf = sum(1 for c in person_confidences if c < 0.5)
        
        print(f"\n置信度分布:")
        print(f"  高置信度 (≥0.8): {high_conf} ({high_conf/len(person_confidences)*100:.1f}%)")
        print(f"  中等置信度 (0.5-0.8): {medium_conf} ({medium_conf/len(person_confidences)*100:.1f}%)")
        print(f"  低置信度 (<0.5): {low_conf} ({low_conf/len(person_confidences)*100:.1f}%)")
    
    # 分析每张图片的人数分布
    print(f"\n=== 每张图片人数分布 ===")
    person_count_dist = {}
    for count in person_counts_per_image:
        person_count_dist[count] = person_count_dist.get(count, 0) + 1
    
    for count in sorted(person_count_dist.keys()):
        percentage = person_count_dist[count] / total_images * 100
        print(f"  {count}人: {person_count_dist[count]}张图片 ({percentage:.1f}%)")
    
    # 分析其他检测到的物体
    print(f"\n=== 其他检测物体统计 ===")
    other_objects = {}
    for result in data['results']:
        for obj in result['other_objects']:
            other_objects[obj] = other_objects.get(obj, 0) + 1
    
    # 按检测次数排序
    sorted_objects = sorted(other_objects.items(), key=lambda x: x[1], reverse=True)
    for obj, count in sorted_objects[:10]:  # 显示前10个
        print(f"  {obj}: {count}次")
    
    # 检测质量评估
    print(f"\n=== 检测质量评估 ===")
    
    # 人员检测评估
    if person_confidences:
        reliable_detections = sum(1 for c in person_confidences if c >= 0.7)
        print(f"可靠的人员检测 (置信度≥0.7): {reliable_detections}/{len(person_confidences)} ({reliable_detections/len(person_confidences)*100:.1f}%)")
    
    # 火源检测评估
    print(f"火源检测: 0次检测，需要自定义训练")
    
    # 建议
    print(f"\n=== 训练建议 ===")
    
    if images_with_person / total_images < 0.6:
        print("❌ 人员检测覆盖率较低，建议进行微调训练")
    elif np.mean(person_confidences) < 0.7:
        print("⚠️  人员检测置信度偏低，建议进行微调训练")
    else:
        print("✅ 人员检测效果较好，可考虑直接使用")
    
    print("❌ 火源检测完全无效，必须进行自定义训练")
    
    # 推荐的训练策略
    print(f"\n=== 推荐训练策略 ===")
    print("1. 人员检测:")
    if np.mean(person_confidences) >= 0.6:
        print("   - 可以使用预训练权重进行微调")
        print("   - 重点标注漏检和误检的案例")
        print("   - 建议标注数据量: 500-1000张")
    else:
        print("   - 需要从头训练或大量微调")
        print("   - 建议标注数据量: 1000-2000张")
    
    print("2. 火源检测:")
    print("   - 必须从头训练")
    print("   - 建议收集更多火源样本")
    print("   - 建议标注数据量: 500-1500张")
    
    return {
        'person_detection_rate': images_with_person / total_images,
        'person_avg_confidence': np.mean(person_confidences) if person_confidences else 0,
        'fire_detection_rate': images_with_fire / total_images,
        'person_confidences': person_confidences,
        'recommendations': {
            'person_training_needed': np.mean(person_confidences) < 0.7 if person_confidences else True,
            'fire_training_needed': True
        }
    }

def visualize_sample_detections(stats_file, num_samples=5):
    """可视化一些检测样本"""
    
    with open(stats_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 找到一些有人员检测的样本
    person_samples = []
    for result in data['results']:
        if result['person_count'] > 0:
            person_samples.append(result)
    
    print(f"\n=== 检测样本可视化 ===")
    print(f"找到 {len(person_samples)} 个包含人员的检测样本")
    
    # 选择置信度最高的几个样本
    person_samples.sort(key=lambda x: max([d['confidence'] for d in x['detections'] if d['class_name'] == 'person']), reverse=True)
    
    for i, sample in enumerate(person_samples[:num_samples]):
        print(f"\n样本 {i+1}: {Path(sample['image_path']).name}")
        print(f"  人数: {sample['person_count']}")
        
        person_detections = [d for d in sample['detections'] if d['class_name'] == 'person']
        for j, detection in enumerate(person_detections):
            print(f"  人员 {j+1}: 置信度 {detection['confidence']:.3f}, 位置 {detection['bbox']}")

if __name__ == "__main__":
    # 找到最新的统计文件
    stats_files = list(Path("test_results").glob("detection_stats_*.json"))
    if not stats_files:
        print("未找到检测统计文件")
        exit(1)
    
    latest_stats = max(stats_files, key=lambda x: x.stat().st_mtime)
    print(f"分析文件: {latest_stats}")
    
    # 分析结果
    analysis = analyze_detection_results(latest_stats)
    
    # 可视化样本
    visualize_sample_detections(latest_stats)
    
    print(f"\n=== 总结 ===")
    print(f"人员检测率: {analysis['person_detection_rate']*100:.1f}%")
    print(f"人员检测平均置信度: {analysis['person_avg_confidence']:.3f}")
    print(f"火源检测率: {analysis['fire_detection_rate']*100:.1f}%")
    
    if analysis['recommendations']['person_training_needed']:
        print("建议: 需要对人员检测进行微调训练")
    else:
        print("建议: 人员检测可以直接使用")
    
    if analysis['recommendations']['fire_training_needed']:
        print("建议: 必须对火源检测进行自定义训练")