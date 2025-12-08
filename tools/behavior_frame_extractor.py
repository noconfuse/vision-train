#!/usr/bin/env python3
"""
行为识别数据集帧提取器
专门用于从监控视频中提取包含人员的帧，用于行为识别模型训练

基于 simple_frame_extractor.py，增加了人员检测功能
"""

import cv2
import os
import logging
import json
import time
from datetime import datetime
from pathlib import Path
import numpy as np
from typing import List, Dict, Tuple, Optional
import argparse
import glob
from tqdm import tqdm

# 尝试导入YOLO用于人员检测
try:
    import ultralytics
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("警告: ultralytics未安装，将使用OpenCV的人员检测器")

# 尝试导入OpenCV的DNN模块用于人员检测
try:
    import cv2.dnn as dnn
    DNN_AVAILABLE = True
except ImportError:
    DNN_AVAILABLE = False


class BehaviorFrameExtractor:
    """行为识别专用帧提取器"""
    
    def __init__(self, output_dir: str = "behavior_dataset", 
                 detection_method: str = "yolo",
                 confidence_threshold: float = 0.5,
                 min_person_size: int = 50):
        """
        初始化行为帧提取器
        
        Args:
            output_dir: 输出目录
            detection_method: 人员检测方法 ('yolo', 'opencv', 'none')
            confidence_threshold: 检测置信度阈值
            min_person_size: 最小人员尺寸（像素）
        """
        self.output_dir = Path(output_dir)
        self.detection_method = detection_method
        self.confidence_threshold = confidence_threshold
        self.min_person_size = min_person_size
        
        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置日志
        self.setup_logging()
        
        # 初始化人员检测器
        self.person_detector = None
        self.setup_person_detector()
        
        # 统计信息
        self.stats = {
            'total_videos': 0,
            'processed_videos': 0,
            'total_frames_checked': 0,
            'frames_with_person': 0,
            'frames_extracted': 0,
            'failed_videos': 0,
            'start_time': None,
            'end_time': None
        }
    
    def setup_logging(self):
        """设置日志系统"""
        # 日志目录放到项目根目录
        project_root = Path(__file__).parent.parent  # 从tools目录回到项目根目录
        logs_dir = project_root / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / f"extraction_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"行为识别帧提取器初始化完成，输出目录: {self.output_dir}")
    
    def setup_person_detector(self):
        """设置人员检测器"""
        if self.detection_method == "none":
            self.logger.info("跳过人员检测，将提取所有帧")
            return
            
        if self.detection_method == "yolo" and YOLO_AVAILABLE:
            try:
                # 使用YOLOv8n模型进行人员检测
                self.person_detector = YOLO('yolov8n.pt')
                self.logger.info("YOLO人员检测器初始化成功")
                return
            except Exception as e:
                self.logger.warning(f"YOLO初始化失败: {e}，尝试使用OpenCV检测器")
        
        if DNN_AVAILABLE:
            try:
                # 使用OpenCV的HOG人员检测器
                self.person_detector = cv2.HOGDescriptorDetector()
                self.person_detector.setSVMDetector(cv2.HOGDescriptorDetector_getDefaultPeopleDetector())
                self.detection_method = "opencv"
                self.logger.info("OpenCV HOG人员检测器初始化成功")
                return
            except Exception as e:
                self.logger.warning(f"OpenCV检测器初始化失败: {e}")
        
        self.logger.warning("无法初始化人员检测器，将提取所有帧")
        self.detection_method = "none"
    
    def detect_person_yolo(self, frame: np.ndarray) -> bool:
        """使用YOLO检测帧中是否有人"""
        try:
            results = self.person_detector(frame, verbose=False)
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    # 检查是否有人类检测（class 0 是人）
                    for box in boxes:
                        if box.cls == 0 and box.conf >= self.confidence_threshold:
                            # 检查检测框大小
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                            width = x2 - x1
                            height = y2 - y1
                            if width >= self.min_person_size and height >= self.min_person_size:
                                return True
            return False
        except Exception as e:
            self.logger.error(f"YOLO检测错误: {e}")
            return False
    
    def detect_person_opencv(self, frame: np.ndarray) -> bool:
        """使用OpenCV HOG检测帧中是否有人"""
        try:
            # 调整图像大小以提高检测速度
            height, width = frame.shape[:2]
            if width > 640:
                scale = 640 / width
                new_width = int(width * scale)
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height))
            
            # 检测人员
            boxes, weights = self.person_detector.detectMultiScale(
                frame, 
                winStride=(8, 8),
                padding=(32, 32),
                scale=1.05
            )
            
            # 检查是否有足够大的检测结果
            for (x, y, w, h), weight in zip(boxes, weights):
                if weight >= self.confidence_threshold and w >= self.min_person_size and h >= self.min_person_size:
                    return True
            
            return False
        except Exception as e:
            self.logger.error(f"OpenCV检测错误: {e}")
            return False
    
    def has_person(self, frame: np.ndarray) -> bool:
        """检测帧中是否有人"""
        if self.detection_method == "none":
            return True
        elif self.detection_method == "yolo":
            return self.detect_person_yolo(frame)
        elif self.detection_method == "opencv":
            return self.detect_person_opencv(frame)
        else:
            return True
    
    def is_valid_frame(self, frame: np.ndarray) -> bool:
        """检查帧是否有效（质量评估）"""
        if frame is None or frame.size == 0:
            return False
        
        # 检查图像尺寸
        height, width = frame.shape[:2]
        if width < 224 or height < 224:  # 行为识别通常需要较大的图像
            return False
        
        # 检查图像亮度（避免过暗或过亮的帧）
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)
        if mean_brightness < 20 or mean_brightness > 235:
            return False
        
        # 检查图像清晰度（拉普拉斯方差）
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if laplacian_var < 100:  # 模糊阈值
            return False
        
        return True
    
    def _estimate_frame_count(self, cap: cv2.VideoCapture) -> int:
        """通过实际读取来估算视频帧数"""
        self.logger.info("正在估算视频帧数...")
        
        # 保存当前位置
        current_pos = cap.get(cv2.CAP_PROP_POS_FRAMES)
        
        # 重置到开始
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        frame_count = 0
        sample_interval = 1000  # 每1000帧采样一次来估算
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1
            
            # 每采样一定帧数后跳跃，加速估算
            if frame_count % sample_interval == 0:
                # 尝试跳跃到下一个采样点
                next_pos = frame_count + sample_interval
                cap.set(cv2.CAP_PROP_POS_FRAMES, next_pos)
                ret, _ = cap.read()
                if not ret:
                    break
                frame_count = next_pos
        
        # 恢复原始位置
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_pos)
        
        self.logger.info(f"估算得到帧数: {frame_count}")
        return max(frame_count, 1)  # 至少返回1帧
    
    def extract_frames_from_video(self, video_path: str, 
                                 max_frames: int = 100,
                                 frame_interval: int = 30) -> Dict:
        """从单个视频中提取包含人员的帧"""
        video_path = Path(video_path)
        video_name = video_path.stem
        
        # 创建扁平化的目录结构 - 图片直接存储在output_dir中
        images_dir = self.output_dir
        
        # 创建所需目录
        images_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"开始处理视频: {video_path}")
        
        # 打开视频，使用更兼容的后端
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            # 尝试使用FFmpeg后端
            cap = cv2.VideoCapture(str(video_path), cv2.CAP_FFMPEG)
            if not cap.isOpened():
                self.logger.error(f"无法打开视频文件: {video_path}")
                return {'success': False, 'error': '无法打开视频文件'}
        
        # 获取视频信息并验证
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # 验证视频信息的有效性
        if total_frames <= 0 or fps <= 0 or width <= 0 or height <= 0:
            self.logger.warning(f"视频元数据异常，尝试通过实际读取帧来获取信息")
            # 通过实际读取来估算帧数
            total_frames = self._estimate_frame_count(cap)
            fps = fps if fps > 0 else 25.0  # 默认25fps
        
        duration = total_frames / fps if fps > 0 else 0
        
        self.logger.info(f"视频信息 - 总帧数: {total_frames}, FPS: {fps:.2f}, 分辨率: {width}x{height}, 时长: {duration:.2f}秒")
        
        extracted_frames = 0
        checked_frames = 0
        frames_with_person = 0
        frame_info = []
        
        # 创建进度条
        pbar = tqdm(total=min(total_frames // frame_interval, max_frames), 
                   desc=f"处理 {video_name}")
        
        try:
            frame_number = 0
            consecutive_failures = 0
            max_consecutive_failures = 50  # 连续失败50次后停止
            
            while extracted_frames < max_frames and frame_number < total_frames:
                # 尝试读取帧，使用更健壮的方法
                success = False
                for attempt in range(3):  # 最多尝试3次
                    try:
                        # 跳到指定帧
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                        ret, frame = cap.read()
                        
                        if ret and frame is not None and frame.size > 0:
                            success = True
                            consecutive_failures = 0
                            break
                        else:
                            # 尝试顺序读取
                            ret, frame = cap.read()
                            if ret and frame is not None and frame.size > 0:
                                success = True
                                consecutive_failures = 0
                                break
                    except Exception as e:
                        self.logger.debug(f"读取帧 {frame_number} 失败 (尝试 {attempt + 1}): {e}")
                        continue
                
                if not success:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        self.logger.warning(f"连续 {max_consecutive_failures} 次读取失败，停止处理")
                        break
                    frame_number += frame_interval
                    continue
                
                checked_frames += 1
                self.stats['total_frames_checked'] += 1
                
                # 检查帧质量
                if not self.is_valid_frame(frame):
                    frame_number += frame_interval
                    continue
                
                # 检测是否有人
                if self.has_person(frame):
                    frames_with_person += 1
                    self.stats['frames_with_person'] += 1
                    
                    # 保存帧
                    timestamp = frame_number / fps if fps > 0 else frame_number
                    frame_filename = f"{video_name}_frame_{frame_number:06d}_t{timestamp:.2f}s.jpg"
                    frame_path = images_dir / frame_filename
                    
                    # 保存高质量图像
                    cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    
                    frame_info.append({
                        'filename': frame_filename,
                        'frame_number': frame_number,
                        'timestamp': timestamp,
                        'video_source': str(video_path)
                    })
                    
                    extracted_frames += 1
                    self.stats['frames_extracted'] += 1
                    
                    pbar.set_postfix({
                        'extracted': extracted_frames,
                        'with_person': frames_with_person,
                        'checked': checked_frames
                    })
                
                frame_number += frame_interval
                pbar.update(1)
                
                # 如果已经检查了足够多的帧但没找到足够的人员帧，增加检查范围
                if checked_frames > max_frames * 3 and extracted_frames < max_frames * 0.1:
                    self.logger.warning(f"视频 {video_name} 中人员帧较少，可能不适合行为识别")
                    break
        
        except Exception as e:
            self.logger.error(f"处理视频 {video_path} 时出错: {e}")
            return {'success': False, 'error': str(e)}
        
        finally:
            cap.release()
            pbar.close()
        
        # 保存帧信息到images目录
        info_file = images_dir / f"{video_name}_frame_info.json"
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump({
                'video_info': {
                    'source_path': str(video_path),
                    'total_frames': total_frames,
                    'fps': fps,
                    'duration': duration
                },
                'extraction_info': {
                    'extracted_frames': extracted_frames,
                    'checked_frames': checked_frames,
                    'frames_with_person': frames_with_person,
                    'detection_method': self.detection_method,
                    'confidence_threshold': self.confidence_threshold
                },
                'frames': frame_info
            }, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"视频 {video_name} 处理完成 - 提取了 {extracted_frames} 帧（检查了 {checked_frames} 帧，{frames_with_person} 帧包含人员）")
        
        return {
            'success': True,
            'extracted_frames': extracted_frames,
            'checked_frames': checked_frames,
            'frames_with_person': frames_with_person,
            'output_dir': str(self.output_dir),
            'images_dir': str(images_dir),
            'info_file': str(info_file)
        }
    
    def process_video_directory(self, video_dir: str, 
                               max_frames_per_video: int = 100,
                               frame_interval: int = 30,
                               video_extensions: List[str] = None) -> Dict:
        """批量处理视频目录"""
        if video_extensions is None:
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
        
        video_dir = Path(video_dir)
        if not video_dir.exists():
            raise ValueError(f"视频目录不存在: {video_dir}")
        
        # 查找所有视频文件
        video_files = []
        for ext in video_extensions:
            video_files.extend(video_dir.glob(f"**/*{ext}"))
            video_files.extend(video_dir.glob(f"**/*{ext.upper()}"))
        
        if not video_files:
            raise ValueError(f"在目录 {video_dir} 中未找到视频文件")
        
        self.stats['total_videos'] = len(video_files)
        self.stats['start_time'] = datetime.now()
        
        self.logger.info(f"找到 {len(video_files)} 个视频文件，开始批量处理")
        
        results = []
        
        for video_file in video_files:
            try:
                result = self.extract_frames_from_video(
                    str(video_file), 
                    max_frames_per_video, 
                    frame_interval
                )
                results.append({
                    'video_path': str(video_file),
                    'result': result
                })
                
                if result['success']:
                    self.stats['processed_videos'] += 1
                else:
                    self.stats['failed_videos'] += 1
                    
            except Exception as e:
                self.logger.error(f"处理视频 {video_file} 时发生错误: {e}")
                self.stats['failed_videos'] += 1
                results.append({
                    'video_path': str(video_file),
                    'result': {'success': False, 'error': str(e)}
                })
        
        self.stats['end_time'] = datetime.now()
        
        # 生成总结报告
        self.generate_summary_report(results)
        
        return {
            'total_videos': len(video_files),
            'processed_videos': self.stats['processed_videos'],
            'failed_videos': self.stats['failed_videos'],
            'total_frames_extracted': self.stats['frames_extracted'],
            'results': results
        }
    
    def generate_summary_report(self, results: List[Dict]):
        """生成处理总结报告"""
        report_file = self.output_dir / f"extraction_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        processing_time = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        report = {
            'extraction_summary': {
                'start_time': self.stats['start_time'].isoformat(),
                'end_time': self.stats['end_time'].isoformat(),
                'processing_time_seconds': processing_time,
                'total_videos': self.stats['total_videos'],
                'processed_videos': self.stats['processed_videos'],
                'failed_videos': self.stats['failed_videos'],
                'total_frames_checked': self.stats['total_frames_checked'],
                'frames_with_person': self.stats['frames_with_person'],
                'total_frames_extracted': self.stats['frames_extracted'],
                'person_detection_rate': self.stats['frames_with_person'] / max(self.stats['total_frames_checked'], 1),
                'extraction_rate': self.stats['frames_extracted'] / max(self.stats['frames_with_person'], 1)
            },
            'configuration': {
                'detection_method': self.detection_method,
                'confidence_threshold': self.confidence_threshold,
                'min_person_size': self.min_person_size,
                'output_directory': str(self.output_dir)
            },
            'detailed_results': results
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # 打印总结
        print("\n" + "="*60)
        print("行为识别数据集提取完成!")
        print("="*60)
        print(f"处理时间: {processing_time:.2f} 秒")
        print(f"总视频数: {self.stats['total_videos']}")
        print(f"成功处理: {self.stats['processed_videos']}")
        print(f"失败视频: {self.stats['failed_videos']}")
        print(f"检查帧数: {self.stats['total_frames_checked']}")
        print(f"包含人员的帧: {self.stats['frames_with_person']}")
        print(f"提取帧数: {self.stats['frames_extracted']}")
        print(f"人员检测率: {self.stats['frames_with_person'] / max(self.stats['total_frames_checked'], 1):.2%}")
        print(f"输出目录: {self.output_dir}")
        print(f"详细报告: {report_file}")
        print("="*60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='行为识别数据集帧提取器')
    parser.add_argument('video_path', help='视频文件路径或包含视频的目录路径')
    parser.add_argument('-o', '--output', default='behavior_dataset', 
                       help='输出目录 (默认: behavior_dataset)')
    parser.add_argument('-m', '--max-frames', type=int, default=100,
                       help='每个视频最大提取帧数 (默认: 100)')
    parser.add_argument('-i', '--interval', type=int, default=30,
                       help='帧间隔 (默认: 30)')
    parser.add_argument('-d', '--detection', choices=['yolo', 'opencv', 'none'], 
                       default='yolo', help='人员检测方法 (默认: yolo)')
    parser.add_argument('-c', '--confidence', type=float, default=0.5,
                       help='检测置信度阈值 (默认: 0.5)')
    parser.add_argument('-s', '--min-size', type=int, default=50,
                       help='最小人员尺寸像素 (默认: 50)')
    
    args = parser.parse_args()
    
    # 创建提取器
    extractor = BehaviorFrameExtractor(
        output_dir=args.output,
        detection_method=args.detection,
        confidence_threshold=args.confidence,
        min_person_size=args.min_size
    )
    
    video_path = Path(args.video_path)
    
    try:
        if video_path.is_file():
            # 处理单个视频文件
            result = extractor.extract_frames_from_video(
                str(video_path), 
                args.max_frames, 
                args.interval
            )
            if result['success']:
                print(f"成功提取 {result['extracted_frames']} 帧到 {result['output_dir']}")
            else:
                print(f"提取失败: {result['error']}")
        
        elif video_path.is_dir():
            # 处理视频目录
            result = extractor.process_video_directory(
                str(video_path),
                args.max_frames,
                args.interval
            )
            print(f"批量处理完成，共处理 {result['processed_videos']} 个视频")
        
        else:
            print(f"错误: 路径 {video_path} 不存在")
            return 1
    
    except Exception as e:
        print(f"处理过程中发生错误: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())