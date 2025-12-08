#!/usr/bin/env python3
"""
智能筛选模块 - 用于智能筛选未标注图片
提供多种筛选策略来优化标注效率
"""

import os
import json
import random
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple
import cv2
from datetime import datetime

class SmartImageFilter:
    """智能图片筛选器"""
    
    def __init__(self, images_dir: str, labels_dir: str, predictor=None):
        self.images_dir = Path(images_dir)
        self.labels_dir = Path(labels_dir)
        self.predictor = predictor
        
    def get_unannotated_images(self) -> List[str]:
        """获取所有未标注的图片"""
        all_images = []
        for ext in ['*.jpg', '*.jpeg', '*.png']:
            all_images.extend(self.images_dir.glob(ext))
        
        unannotated = []
        for img_path in all_images:
            label_path = self.labels_dir / f"{img_path.stem}.txt"
            if not label_path.exists():
                unannotated.append(img_path.name)
        
        return unannotated
    
    def filter_by_diversity(self, images: List[str], max_count: int = 100) -> List[str]:
        """基于图片多样性筛选 - 选择视觉特征差异较大的图片"""
        if len(images) <= max_count:
            return images
            
        # 计算图片的基本特征（颜色直方图、边缘密度等）
        features = []
        valid_images = []
        
        for img_name in images:
            img_path = self.images_dir / img_name
            try:
                img = cv2.imread(str(img_path))
                if img is None:
                    continue
                    
                # 计算颜色直方图
                hist_b = cv2.calcHist([img], [0], None, [32], [0, 256])
                hist_g = cv2.calcHist([img], [1], None, [32], [0, 256])
                hist_r = cv2.calcHist([img], [2], None, [32], [0, 256])
                
                # 计算边缘密度
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, 50, 150)
                edge_density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])
                
                # 计算亮度均值和标准差
                brightness_mean = np.mean(gray)
                brightness_std = np.std(gray)
                
                # 组合特征向量
                feature = np.concatenate([
                    hist_b.flatten(), hist_g.flatten(), hist_r.flatten(),
                    [edge_density, brightness_mean, brightness_std]
                ])
                
                features.append(feature)
                valid_images.append(img_name)
                
            except Exception as e:
                print(f"处理图片 {img_name} 时出错: {e}")
                continue
        
        if len(valid_images) <= max_count:
            return valid_images
            
        # 使用K-means聚类选择多样性图片
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        
        # 标准化特征
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)
        
        # 聚类
        n_clusters = min(max_count, len(features_scaled))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        clusters = kmeans.fit_predict(features_scaled)
        
        # 从每个聚类中选择最接近聚类中心的图片
        selected = []
        for i in range(n_clusters):
            cluster_indices = np.where(clusters == i)[0]
            if len(cluster_indices) > 0:
                # 找到最接近聚类中心的点
                center = kmeans.cluster_centers_[i]
                distances = [np.linalg.norm(features_scaled[idx] - center) for idx in cluster_indices]
                closest_idx = cluster_indices[np.argmin(distances)]
                selected.append(valid_images[closest_idx])
        
        return selected[:max_count]
    
    def filter_by_prediction_confidence(self, images: List[str], max_count: int = 100, 
                                      confidence_range: Tuple[float, float] = (0.3, 0.7)) -> List[str]:
        """基于预测置信度筛选 - 选择置信度在特定范围内的图片（不确定性采样）"""
        if not self.predictor or len(images) <= max_count:
            return images[:max_count]
        
        image_scores = []
        
        for img_name in images:
            img_path = self.images_dir / img_name
            try:
                predictions = self.predictor.predict_image(str(img_path))
                
                if predictions:
                    # 计算平均置信度
                    confidences = [pred.get('confidence', 0) for pred in predictions]
                    avg_confidence = np.mean(confidences)
                    
                    # 检查是否在目标置信度范围内
                    if confidence_range[0] <= avg_confidence <= confidence_range[1]:
                        # 使用不确定性分数（越接近0.5越不确定）
                        uncertainty_score = 1 - abs(avg_confidence - 0.5) * 2
                        image_scores.append((img_name, uncertainty_score, avg_confidence))
                else:
                    # 没有预测结果的图片也值得标注
                    image_scores.append((img_name, 1.0, 0.0))
                    
            except Exception as e:
                print(f"预测图片 {img_name} 时出错: {e}")
                continue
        
        # 按不确定性分数排序，选择最不确定的图片
        image_scores.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in image_scores[:max_count]]
    
    def filter_by_random_sampling(self, images: List[str], max_count: int = 100) -> List[str]:
        """随机采样筛选"""
        if len(images) <= max_count:
            return images
        return random.sample(images, max_count)
    
    def filter_by_time_based(self, images: List[str], max_count: int = 100, 
                           strategy: str = 'newest') -> List[str]:
        """基于时间的筛选"""
        image_times = []
        
        for img_name in images:
            img_path = self.images_dir / img_name
            try:
                stat = img_path.stat()
                mtime = stat.st_mtime
                image_times.append((img_name, mtime))
            except Exception:
                continue
        
        # 按时间排序
        reverse = (strategy == 'newest')
        image_times.sort(key=lambda x: x[1], reverse=reverse)
        
        return [item[0] for item in image_times[:max_count]]
    
    def smart_filter(self, strategy: str = 'diversity', max_count: int = 100, 
                    **kwargs) -> Dict[str, Any]:
        """智能筛选主函数"""
        unannotated_images = self.get_unannotated_images()
        
        if not unannotated_images:
            return {
                'success': True,
                'strategy': strategy,
                'total_unannotated': 0,
                'selected_images': [],
                'message': '没有未标注的图片'
            }
        
        # 根据策略筛选
        if strategy == 'diversity':
            selected = self.filter_by_diversity(unannotated_images, max_count)
        elif strategy == 'uncertainty':
            confidence_range = kwargs.get('confidence_range', (0.3, 0.7))
            selected = self.filter_by_prediction_confidence(
                unannotated_images, max_count, confidence_range
            )
        elif strategy == 'random':
            selected = self.filter_by_random_sampling(unannotated_images, max_count)
        elif strategy == 'newest':
            selected = self.filter_by_time_based(unannotated_images, max_count, 'newest')
        elif strategy == 'oldest':
            selected = self.filter_by_time_based(unannotated_images, max_count, 'oldest')
        else:
            # 默认使用多样性筛选
            selected = self.filter_by_diversity(unannotated_images, max_count)
        
        return {
            'success': True,
            'strategy': strategy,
            'total_unannotated': len(unannotated_images),
            'selected_count': len(selected),
            'selected_images': selected,
            'message': f'使用 {strategy} 策略筛选出 {len(selected)} 张图片'
        }
    
    def filter_images(self, strategy: str = 'diversity', max_count: int = 100, 
                     confidence_range: Tuple[float, float] = (0.3, 0.7)) -> List[str]:
        """筛选图片并返回图片名称列表"""
        result = self.smart_filter(strategy=strategy, max_count=max_count, 
                                 confidence_range=confidence_range)
        return result.get('selected_images', [])