#!/usr/bin/env python3
"""
监控YOLOv11m火焰检测模型训练进度
"""

import os
import time
import subprocess
from pathlib import Path

def check_training_status():
    """检查训练状态"""
    print("🔍 检查训练进程状态...")
    
    # 检查进程是否运行
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if 'train_fire_detection_m.py' in result.stdout:
            print("✅ 训练进程正在运行")
            
            # 提取进程信息
            lines = result.stdout.split('\n')
            for line in lines:
                if 'train_fire_detection_m.py' in line:
                    parts = line.split()
                    cpu_usage = parts[2]
                    memory_usage = parts[3]
                    print(f"   📊 CPU使用率: {cpu_usage}%")
                    print(f"   💾 内存使用率: {memory_usage}%")
                    break
        else:
            print("❌ 训练进程未运行")
            return False
    except Exception as e:
        print(f"❌ 检查进程状态失败: {e}")
        return False
    
    return True

def show_training_log():
    """显示训练日志"""
    log_file = Path("training_m.log")
    
    if not log_file.exists():
        print("❌ 训练日志文件不存在")
        return
    
    print("\n📋 最新训练日志 (最后20行):")
    print("-" * 60)
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-20:]:
                print(line.rstrip())
    except Exception as e:
        print(f"❌ 读取日志文件失败: {e}")

def show_training_progress():
    """显示训练进度"""
    output_dir = Path("models/layer1_base_detection/outputs/fire_training_m/fire_detection_m_run")
    
    if not output_dir.exists():
        print("❌ 训练输出目录不存在")
        return
    
    # 检查results.csv文件
    results_file = output_dir / "results.csv"
    if results_file.exists():
        print("\n📈 训练进度:")
        print("-" * 60)
        
        try:
            with open(results_file, 'r') as f:
                lines = f.readlines()
                if len(lines) > 1:
                    # 显示表头
                    print(lines[0].strip())
                    # 显示最后几行
                    for line in lines[-3:]:
                        print(line.strip())
                else:
                    print("训练刚开始，暂无进度数据")
        except Exception as e:
            print(f"❌ 读取进度文件失败: {e}")
    else:
        print("📊 训练进度文件尚未生成")

def show_model_files():
    """显示已生成的模型文件"""
    weights_dir = Path("models/layer1_base_detection/outputs/fire_training_m/fire_detection_m_run/weights")
    
    if weights_dir.exists():
        print("\n🎯 已生成的模型文件:")
        print("-" * 60)
        
        model_files = list(weights_dir.glob("*.pt"))
        if model_files:
            for model_file in sorted(model_files):
                size = model_file.stat().st_size / (1024 * 1024)  # MB
                mtime = time.ctime(model_file.stat().st_mtime)
                print(f"   📁 {model_file.name} ({size:.1f}MB) - {mtime}")
        else:
            print("   暂无模型文件生成")
    else:
        print("📁 模型权重目录尚未创建")

def main():
    print("🔥 YOLOv11m火焰检测模型训练监控")
    print("=" * 60)
    
    # 检查训练状态
    is_running = check_training_status()
    
    # 显示训练日志
    show_training_log()
    
    # 显示训练进度
    show_training_progress()
    
    # 显示模型文件
    show_model_files()
    
    print("\n" + "=" * 60)
    if is_running:
        print("💡 训练正在进行中，你可以安全关闭终端")
        print("💡 使用 'python monitor_training_m.py' 随时查看进度")
        print("💡 训练日志保存在: training_m.log")
        print("💡 模型输出目录: models/layer1_base_detection/outputs/fire_training_m/")
    else:
        print("⚠️ 训练进程未运行，请检查是否出现错误")

if __name__ == "__main__":
    main()