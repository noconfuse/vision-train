#!/usr/bin/env python3
"""
行为预测模型接口
提供智能预标注和行为识别辅助功能
"""

import os
import cv2
import numpy as np
import torch
from pathlib import Path
import json
from datetime import datetime
import logging
from behavior_config import get_behavior_classes

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_latest_incremental_model():
    """查找最新的增量训练模型"""
    try:
        # 增量训练模型存储路径
        project_root = Path(__file__).parent.parent.parent.parent
        training_dir = project_root / "models/layer3_behavior_detection/datasets/workflow_behaviors/train"
        
        if not training_dir.exists():
            logger.warning(f"训练目录不存在: {training_dir}")
            return None
        
        # 查找所有incremental_xxx目录
        incremental_dirs = [d for d in training_dir.iterdir() 
                           if d.is_dir() and d.name.startswith('incremental_')]
        
        if not incremental_dirs:
            logger.info("未找到增量训练目录")
            return None
        
        # 按修改时间排序，获取最新的
        latest_dir = max(incremental_dirs, key=lambda x: x.stat().st_mtime)
        
        # 查找weights/best.pt文件
        weights_dir = latest_dir / 'weights'
        if weights_dir.exists():
            best_model = weights_dir / 'best.pt'
            if best_model.exists():
                logger.info(f"找到最新增量训练模型: {best_model}")
                return str(best_model)
        
        logger.warning(f"在最新训练目录中未找到best.pt: {latest_dir}")
        return None
        
    except Exception as e:
        logger.error(f"查找增量训练模型失败: {e}")
        return None

def calculate_iou(box1, box2):
    """
    计算两个边界框的IoU (Intersection over Union)
    
    Args:
        box1, box2: 边界框，格式为 [x_center, y_center, width, height] (归一化坐标)
    
    Returns:
        float: IoU值
    """
    # 转换为 [x1, y1, x2, y2] 格式
    x1_1 = box1[0] - box1[2] / 2
    y1_1 = box1[1] - box1[3] / 2
    x2_1 = box1[0] + box1[2] / 2
    y2_1 = box1[1] + box1[3] / 2
    
    x1_2 = box2[0] - box2[2] / 2
    y1_2 = box2[1] - box2[3] / 2
    x2_2 = box2[0] + box2[2] / 2
    y2_2 = box2[1] + box2[3] / 2
    
    # 计算交集
    x1_inter = max(x1_1, x1_2)
    y1_inter = max(y1_1, y1_2)
    x2_inter = min(x2_1, x2_2)
    y2_inter = min(y2_1, y2_2)
    
    if x2_inter <= x1_inter or y2_inter <= y1_inter:
        return 0.0
    
    inter_area = (x2_inter - x1_inter) * (y2_inter - y1_inter)
    
    # 计算并集
    area1 = box1[2] * box1[3]
    area2 = box2[2] * box2[3]
    union_area = area1 + area2 - inter_area
    
    if union_area <= 0:
        return 0.0
    
    return inter_area / union_area

def apply_nms(predictions, iou_threshold=0.5, confidence_threshold=0.15):
    """
    应用非极大值抑制 (NMS) 去除重叠的检测框
    
    Args:
        predictions: 预测结果列表
        iou_threshold: IoU阈值，超过此值的重叠框会被抑制
        confidence_threshold: 置信度阈值，低于此值的预测会被过滤
    
    Returns:
        list: 经过NMS处理的预测结果
    """
    if not predictions:
        return []
    
    # 首先过滤低置信度的预测
    filtered_predictions = [p for p in predictions if p['confidence'] >= confidence_threshold]
    
    if not filtered_predictions:
        return []
    
    # 按置信度降序排序
    filtered_predictions.sort(key=lambda x: x['confidence'], reverse=True)
    
    # 按类别分组进行NMS
    class_groups = {}
    for pred in filtered_predictions:
        class_id = pred['class_id']
        if class_id not in class_groups:
            class_groups[class_id] = []
        class_groups[class_id].append(pred)
    
    final_predictions = []
    
    # 对每个类别单独应用NMS
    for class_id, class_predictions in class_groups.items():
        if not class_predictions:
            continue
            
        # 已经按置信度排序，现在应用NMS
        keep = []
        
        while class_predictions:
            # 取置信度最高的预测
            current = class_predictions.pop(0)
            keep.append(current)
            
            # 移除与当前预测重叠度过高的其他预测
            remaining = []
            for pred in class_predictions:
                current_box = [current['x_center'], current['y_center'], current['width'], current['height']]
                pred_box = [pred['x_center'], pred['y_center'], pred['width'], pred['height']]
                
                iou = calculate_iou(current_box, pred_box)
                if iou <= iou_threshold:
                    remaining.append(pred)
                # else: 重叠度过高，抑制这个预测
            
            class_predictions = remaining
        
        final_predictions.extend(keep)
    
    # 最终按置信度排序
    final_predictions.sort(key=lambda x: x['confidence'], reverse=True)
    
    logger.info(f"NMS处理: {len(predictions)} -> {len(final_predictions)} 个预测结果")
    return final_predictions

class BehaviorPredictor:
    """行为预测器"""
    
    def __init__(self, model_path=None):
        self.model_path = model_path
        self.model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.is_loaded = False
        
        # 行为类别映射 - 从统一配置文件获取
        self.behavior_classes = get_behavior_classes()
        
        # NMS参数
        self.nms_iou_threshold = 0.5  # IoU阈值
        self.nms_confidence_threshold = 0.15  # 置信度阈值 (降低以包含更多预测结果)
        
        # 尝试加载模型
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)


        
        # 尝试加载模型
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
    
    def load_model(self, model_path):
        """加载预训练模型"""
        try:
            logger.info(f"正在加载模型: {model_path}")
            
            # 转换为字符串路径
            model_path_str = str(model_path)
            
            # 检查是否为YOLO模型
            if model_path_str.endswith('.pt'):
                try:
                    from ultralytics import YOLO
                    self.model = YOLO(model_path_str)
                    self.is_loaded = True
                    logger.info("YOLO模型加载成功")
                except ImportError:
                    logger.warning("ultralytics未安装，无法加载YOLO模型")
                except Exception as e:
                    logger.error(f"YOLO模型加载失败: {e}")
            
            self.model_path = model_path_str
            
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            self.is_loaded = False
    
    def predict_behavior_from_scene(self, image_path, image_name=""):
        """使用YOLO模型预测行为"""
        predictions = []
        
        try:
            # 只使用训练好的YOLO模型进行预测
            if self.is_loaded and self.model and os.path.exists(image_path):
                predictions = self._predict_from_model(image_path)
            else:
                logger.warning(f"模型未加载或图像文件不存在: {image_path}")
            
        except Exception as e:
            logger.error(f"YOLO模型预测失败: {e}")
        
        return predictions
    

    

    
    def _predict_from_model(self, image_path):
        """使用训练好的模型进行预测"""
        predictions = []
        
        try:
            if not self.is_loaded or not self.model:
                return predictions
            
            # 使用YOLO模型进行预测，设置较低的置信度阈值
            results = self.model(image_path, verbose=False, conf=0.1)
            
            for result in results:
                if hasattr(result, 'boxes') and result.boxes is not None:
                    boxes = result.boxes
                    
                    for i in range(len(boxes)):
                        # 获取预测结果
                        class_id = int(boxes.cls[i].item())
                        confidence = float(boxes.conf[i].item())
                        
                        # 获取边界框坐标 (xyxy格式)
                        x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                        
                        # 转换为YOLO格式 (中心点 + 宽高)
                        img_height, img_width = result.orig_shape
                        x_center = (x1 + x2) / 2 / img_width
                        y_center = (y1 + y2) / 2 / img_height
                        width = (x2 - x1) / img_width
                        height = (y2 - y1) / img_height
                        
                        if class_id in self.behavior_classes and confidence > 0.1:
                            predictions.append({
                                'class_id': class_id,
                                'class_name': self.behavior_classes[class_id],
                                'confidence': confidence,
                                'source': 'model',
                                'reason': f'模型预测 (置信度: {confidence:.2f})',
                                'x_center': x_center,
                                'y_center': y_center,
                                'width': width,
                                'height': height
                            })
            
            # 应用NMS去除重叠的检测框
            predictions = apply_nms(predictions, self.nms_iou_threshold, self.nms_confidence_threshold)
            
        except Exception as e:
            logger.error(f"模型预测失败: {e}")
        
        return predictions
    
    def _merge_predictions(self, predictions):
        """排序预测结果"""
        # 直接按置信度排序，不进行类别去重
        # 因为一张图片中可能有多个相同类别的行为（如多个人行走）
        predictions.sort(key=lambda x: x['confidence'], reverse=True)
        
        # 返回所有预测结果，不限制数量
        return predictions
    
    def predict_image(self, image_path):
        """
        预测图片中的行为（为了兼容 behavior_annotator.py 的调用）
        
        Args:
            image_path: 图片路径
            
        Returns:
            list: 预测结果列表，包含真实的边界框数据
        """
        try:
            image_name = os.path.basename(image_path)
            predictions = self.predict_behavior_from_scene(image_path, image_name)
            
            # 转换为标注格式
            annotations = []
            for pred in predictions:
                if pred['confidence'] > 0.1:  # 临时降低阈值以便测试AI预测功能
                    annotation = {
                        'class_id': pred['class_id'],
                        'class_name': pred['class_name'],
                        'confidence': pred['confidence'],
                        'source': pred.get('source', 'ai_prediction'),
                        'x_center': pred.get('x_center', 0.5),
                        'y_center': pred.get('y_center', 0.5),
                        'width': pred.get('width', 0.3),
                        'height': pred.get('height', 0.3)
                    }
                    annotations.append(annotation)
            
            return annotations
        except Exception as e:
            logger.error(f"图片预测失败: {e}")
            return []

    
    def update_model_with_feedback(self, image_path, true_annotations, predicted_annotations):
        """使用反馈更新模型（为增量学习准备）"""
        feedback_data = {
            'timestamp': datetime.now().isoformat(),
            'image_path': image_path,
            'true_annotations': true_annotations,
            'predicted_annotations': predicted_annotations,
            'accuracy': self._calculate_accuracy(true_annotations, predicted_annotations)
        }
        
        # 保存反馈数据用于后续训练
        feedback_file = os.path.join(
            os.path.dirname(__file__), 
            'cache', 
            'model_feedback.jsonl'
        )
        
        os.makedirs(os.path.dirname(feedback_file), exist_ok=True)
        
        with open(feedback_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(feedback_data, ensure_ascii=False) + '\n')
        
        logger.info(f"反馈数据已保存: {feedback_file}")
    
    def _calculate_accuracy(self, true_annotations, predicted_annotations):
        """计算预测准确率"""
        if not true_annotations or not predicted_annotations:
            return 0.0
        
        true_classes = set(ann['class_id'] for ann in true_annotations)
        pred_classes = set(ann['class_id'] for ann in predicted_annotations)
        
        if not true_classes:
            return 0.0
        
        intersection = len(true_classes.intersection(pred_classes))
        union = len(true_classes.union(pred_classes))
        
        return intersection / union if union > 0 else 0.0

# 全局预测器实例
behavior_predictor = None

def get_behavior_predictor(model_path=None):
    """获取行为预测器实例"""
    global behavior_predictor
    
    if behavior_predictor is None:
        # 尝试查找可用的模型
        if model_path is None:
            # 优先使用最新的增量训练模型
            latest_incremental_model = find_latest_incremental_model()
            
            if latest_incremental_model:
                model_path = latest_incremental_model
                logger.info(f"使用最新增量训练模型: {model_path}")
            else:
                # 如果没有增量训练模型，使用原始预训练模型
                project_root = Path(__file__).parent.parent.parent.parent
                possible_models = [
                    project_root / "yolo11m.pt"  # 通用YOLO模型
                ]
                
                for model_path in possible_models:
                    if model_path.exists():
                        logger.info(f"使用预训练模型: {model_path}")
                        break
                else:
                    model_path = None
                    logger.warning("未找到任何可用的模型")
        
        behavior_predictor = BehaviorPredictor(model_path)
    
    return behavior_predictor

if __name__ == '__main__':
    # 测试预测器
    predictor = get_behavior_predictor()
    
    print("🤖 行为预测器测试")
    print(f"模型加载状态: {'✅' if predictor.is_loaded else '❌'}")
    print(f"设备: {predictor.device}")
    print(f"支持的行为类别: {len(predictor.behavior_classes)}")
    
    if predictor.is_loaded:
        print("\n✅ YOLO模型已加载，可以进行AI预测")
    else:
        print("\n❌ YOLO模型未加载，请检查模型路径")