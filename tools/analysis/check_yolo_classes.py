#!/usr/bin/env python3
"""
查看YOLO预训练模型的类别定义
"""

from ultralytics import YOLO

def check_yolo_classes():
    """检查YOLO预训练模型的类别"""
    
    # 加载预训练模型
    model = YOLO("yolo11n.pt")
    
    print("=== YOLO预训练模型类别信息 ===\n")
    print(f"模型名称: yolo11n.pt")
    print(f"总类别数: {len(model.names)}")
    print(f"模型架构: {model.model}")
    
    print("\n=== 所有类别列表 ===")
    for class_id, class_name in model.names.items():
        print(f"ID {class_id:2d}: {class_name}")
    
    print("\n=== 重点关注的类别 ===")
    target_classes = ['person', 'fire', 'flame', 'smoke']
    
    for target in target_classes:
        found_classes = []
        for class_id, class_name in model.names.items():
            if target.lower() in class_name.lower():
                found_classes.append(f"ID {class_id}: {class_name}")
        
        if found_classes:
            print(f"\n'{target}' 相关类别:")
            for found in found_classes:
                print(f"  {found}")
        else:
            print(f"\n'{target}' 相关类别: 未找到")
    
    print("\n=== 数据集信息 ===")
    print("YOLO11预训练模型基于COCO数据集训练")
    print("COCO数据集包含80个常见物体类别")
    print("其中 'person' (ID: 0) 是最基础的检测类别之一")
    print("COCO数据集中没有 'fire' 或 'flame' 类别")

if __name__ == "__main__":
    check_yolo_classes()