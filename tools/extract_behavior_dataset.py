#!/usr/bin/env python3
"""
行为识别数据集提取示例脚本
展示如何使用 BehaviorFrameExtractor 从监控视频中提取包含人员的帧
"""

import os
import sys
import argparse
from pathlib import Path

# 添加当前目录到Python路径，以便导入behavior_frame_extractor
sys.path.append(str(Path(__file__).parent))

from behavior_frame_extractor import BehaviorFrameExtractor

def extract_from_surveillance_videos():
    """从监控视频中提取行为识别数据集"""
    
    # 配置参数
    config = {
        # 视频源目录 - 请根据实际情况修改
        'video_directory': '/media/paul/精神世界/视频',  # 你的监控视频硬盘路径
        
        # 输出目录 - 直接输出到workflow_behaviors/train/images/
        'output_directory': '/home/paul/worksapce/vision-train/models/layer3_behavior_detection/datasets/workflow_behaviors/train/images',
        
        # 提取参数
        'max_frames_per_video': 200,  # 每个视频最多提取200帧
        'frame_interval': 60,         # 每60帧检查一次（约2秒间隔，假设30fps）
        
        # 人员检测参数
        'detection_method': 'yolo',   # 使用YOLO进行人员检测
        'confidence_threshold': 0.6,  # 检测置信度阈值
        'min_person_size': 80,        # 最小人员尺寸（像素）
    }
    
    print("="*60)
    print("行为识别数据集提取工具")
    print("="*60)
    print(f"视频源目录: {config['video_directory']}")
    print(f"输出目录: {config['output_directory']}")
    print(f"检测方法: {config['detection_method']}")
    print(f"每视频最大帧数: {config['max_frames_per_video']}")
    print(f"帧间隔: {config['frame_interval']}")
    print("="*60)
    
    # 检查视频目录是否存在
    if not os.path.exists(config['video_directory']):
        print(f"错误: 视频目录不存在: {config['video_directory']}")
        print("请检查硬盘是否正确挂载，或修改脚本中的video_directory路径")
        return False
    
    try:
        # 创建帧提取器
        extractor = BehaviorFrameExtractor(
            output_dir=config['output_directory'],
            detection_method=config['detection_method'],
            confidence_threshold=config['confidence_threshold'],
            min_person_size=config['min_person_size']
        )
        
        # 开始批量处理
        print("开始处理监控视频...")
        result = extractor.process_video_directory(
            video_dir=config['video_directory'],
            max_frames_per_video=config['max_frames_per_video'],
            frame_interval=config['frame_interval']
        )
        
        # 显示结果
        print("\n处理完成!")
        print(f"总视频数: {result['total_videos']}")
        print(f"成功处理: {result['processed_videos']}")
        print(f"失败视频: {result['failed_videos']}")
        print(f"总提取帧数: {result['total_frames_extracted']}")
        
        if result['total_frames_extracted'] > 0:
            print(f"\n数据集已保存到: {config['output_directory']}")
            print("可以开始进行行为识别模型训练了!")
        else:
            print("\n警告: 没有提取到任何帧，请检查:")
            print("1. 视频文件是否存在且可读")
            print("2. 视频中是否包含人员")
            print("3. 检测参数是否合适")
        
        return True
        
    except Exception as e:
        print(f"处理过程中发生错误: {e}")
        return False


def extract_from_surveillance_videos_with_args(args):
    """使用命令行参数从监控视频中提取行为识别数据集"""
    
    # 使用命令行参数配置
    config = {
        'video_directory': args.video_dir,
        'output_directory': args.output_dir,
        'max_frames_per_video': args.max_frames,
        'frame_interval': args.frame_interval,
        'detection_method': args.detection_method,
        'confidence_threshold': args.confidence,
        'min_person_size': args.min_size,
    }
    
    print("="*60)
    print("行为识别数据集提取工具")
    print("="*60)
    print(f"视频源目录: {config['video_directory']}")
    print(f"输出目录: {config['output_directory']}")
    print(f"每个视频最大提取帧数: {config['max_frames_per_video']}")
    print(f"帧间隔: {config['frame_interval']}")
    print(f"检测方法: {config['detection_method']}")
    print(f"置信度阈值: {config['confidence_threshold']}")
    print(f"最小人员尺寸: {config['min_person_size']}")
    print("="*60)
    
    # 检查视频目录是否存在
    if not os.path.exists(config['video_directory']):
        print(f"❌ 错误: 视频目录不存在: {config['video_directory']}")
        return False
    
    try:
        # 创建提取器
        extractor = BehaviorFrameExtractor(
            output_dir=config['output_directory'],
            detection_method=config['detection_method'],
            confidence_threshold=config['confidence_threshold'],
            min_person_size=config['min_person_size']
        )
        
        # 批量处理视频目录
        results = extractor.process_video_directory(
            video_dir=config['video_directory'],
            max_frames_per_video=config['max_frames_per_video'],
            frame_interval=config['frame_interval']
        )
        
        if results['success']:
            print(f"\n✅ 批量处理完成!")
            print(f"处理了 {results['total_videos']} 个视频")
            print(f"成功处理 {results['successful_videos']} 个")
            print(f"总共提取 {results['total_extracted_frames']} 帧")
            print(f"详细报告已保存到: {results.get('report_file', '未知')}")
        else:
            print(f"❌ 批量处理失败: {results['error']}")
        
        return results['success']
        
    except Exception as e:
        print(f"❌ 批量处理时发生错误: {e}")
        return False


def extract_from_single_video_with_args(args):
    """使用命令行参数从单个视频文件提取帧"""
    
    # 示例：处理单个视频文件
    video_path = "/media/paul/精神世界/视频/人工制样室01_20250910102651/人工制样室01_20250404083250-20250404092854_4.mp4"
    
    if not os.path.exists(video_path):
        print(f"示例视频文件不存在: {video_path}")
        print("请修改video_path为实际的视频文件路径")
        return False
    
    try:
        # 创建提取器
        extractor = BehaviorFrameExtractor(
            output_dir=args.output_dir,
            detection_method=args.detection_method,
            confidence_threshold=args.confidence,
            min_person_size=args.min_size
        )
        
        # 提取帧
        result = extractor.extract_frames_from_video(
            video_path=video_path,
            max_frames=args.max_frames,
            frame_interval=args.frame_interval
        )
        
        if result['success']:
            print(f"成功从视频中提取 {result['extracted_frames']} 帧")
            print(f"输出目录: {result['output_dir']}")
        else:
            print(f"提取失败: {result['error']}")
        
        return result['success']
        
    except Exception as e:
        print(f"处理单个视频时发生错误: {e}")
        return False


def extract_from_single_video():
    """从单个视频文件提取帧的示例"""
    
    # 示例：处理单个视频文件
    video_path = "/media/paul/精神世界/视频/人工制样室01_20250910102651/人工制样室01_20250404083250-20250404092854_4.mp4"
    output_dir = "/home/paul/worksapce/vision-train/models/layer3_behavior_detection/datasets/workflow_behaviors/train/images"
    
    if not os.path.exists(video_path):
        print(f"示例视频文件不存在: {video_path}")
        print("请修改video_path为实际的视频文件路径")
        return False
    
    try:
        # 创建提取器
        extractor = BehaviorFrameExtractor(
            output_dir=output_dir,
            detection_method='yolo',
            confidence_threshold=0.5,
            min_person_size=60
        )
        
        # 提取帧
        result = extractor.extract_frames_from_video(
            video_path=video_path,
            max_frames=50,  # 提取50帧用于测试
            frame_interval=30
        )
        
        if result['success']:
            print(f"成功从视频中提取 {result['extracted_frames']} 帧")
            print(f"输出目录: {result['output_dir']}")
        else:
            print(f"提取失败: {result['error']}")
        
        return result['success']
        
    except Exception as e:
        print(f"处理单个视频时发生错误: {e}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='行为识别数据集提取工具')
    parser.add_argument('--mode', '-m', choices=['batch', 'single', 'help'], 
                       default='batch', help='处理模式: batch=批量处理, single=单个视频, help=显示帮助')
    parser.add_argument('--video-dir', '-v', type=str, 
                       default='/media/paul/精神世界/视频',
                       help='监控视频目录路径')
    parser.add_argument('--output-dir', '-o', type=str,
                       default='/home/paul/worksapce/vision-train/models/layer3_behavior_detection/datasets/workflow_behaviors/train/images',
                       help='输出目录路径')
    parser.add_argument('--max-frames', '-f', type=int, default=200,
                       help='每个视频最大提取帧数')
    parser.add_argument('--frame-interval', '-i', type=int, default=60,
                       help='帧间隔（每N帧检查一次）')
    parser.add_argument('--confidence', '-c', type=float, default=0.6,
                       help='人员检测置信度阈值')
    parser.add_argument('--min-size', '-s', type=int, default=80,
                       help='最小人员尺寸（像素）')
    parser.add_argument('--detection-method', '-d', choices=['yolo', 'opencv', 'none'],
                       default='yolo', help='人员检测方法')
    
    args = parser.parse_args()
    
    if args.mode == 'help':
        show_help()
        return
    elif args.mode == 'batch':
        print("\n开始批量处理监控视频...")
        success = extract_from_surveillance_videos_with_args(args)
    elif args.mode == 'single':
        print("\n开始处理单个视频文件...")
        success = extract_from_single_video_with_args(args)
    else:
        print("无效模式，请使用 --help 查看帮助")
        return
    
    if success:
        print("\n✅ 处理完成!")
    else:
        print("\n❌ 处理失败，请检查错误信息")


def show_help():
    """显示帮助信息"""
    help_text = """
行为识别数据集提取工具使用说明
=====================================

功能特点:
- 自动检测视频中的人员
- 只提取包含人员的高质量帧
- 支持批量处理多个视频
- 智能选择输出目录（工作流程行为 vs 违规行为）
- 提供详细的处理报告和统计信息
- 支持多种人员检测方法 (YOLO, OpenCV)

使用方法:
1. 确保已安装依赖包:
   pip install opencv-python ultralytics tqdm numpy

2. 运行脚本并选择操作模式:
   - 模式1: 批量处理监控视频目录
   - 模式2: 处理单个视频文件（测试）
   - 模式3: 显示数据集目录结构
   - 模式4: 显示帮助信息

3. 选择行为类别:
   - 工作流程行为: 筛煤、称重、记录、装载、检查
   - 违规行为: 吸烟、玩手机、吐痰

3. 运行脚本:
   python extract_behavior_dataset.py

参数说明:
- max_frames_per_video: 每个视频最大提取帧数
- frame_interval: 帧间隔（数值越小检查越密集）
- detection_method: 人员检测方法 ('yolo', 'opencv', 'none')
- confidence_threshold: 检测置信度阈值 (0.0-1.0)
- min_person_size: 最小人员尺寸（像素）

输出结构:
behavior_dataset/
├── video1/
│   ├── video1_frame_000030_t1.00s.jpg
│   ├── video1_frame_000060_t2.00s.jpg
│   └── video1_frame_info.json
├── video2/
│   └── ...
└── extraction_report_YYYYMMDD_HHMMSS.json

注意事项:
- 确保有足够的磁盘空间存储提取的帧
- YOLO模型首次运行时会自动下载
- 处理大量视频可能需要较长时间
- 建议先用单个视频测试参数设置
"""
    print(help_text)


if __name__ == "__main__":
    main()