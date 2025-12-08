#!/usr/bin/env python3
"""
行为识别帧提取器依赖安装脚本
"""

import subprocess
import sys
import importlib

def check_package(package_name, import_name=None):
    """检查包是否已安装"""
    if import_name is None:
        import_name = package_name
    
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False

def install_package(package_name):
    """安装包"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    """主函数"""
    print("检查并安装行为识别帧提取器所需依赖...")
    print("="*50)
    
    # 必需的包
    required_packages = [
        ("opencv-python", "cv2"),
        ("numpy", "numpy"),
        ("tqdm", "tqdm"),
        ("ultralytics", "ultralytics"),  # YOLO
        ("Pillow", "PIL"),  # 图像处理
    ]
    
    # 可选的包
    optional_packages = [
        ("matplotlib", "matplotlib"),  # 可视化
        ("seaborn", "seaborn"),       # 统计图表
    ]
    
    all_installed = True
    
    # 检查必需包
    print("检查必需依赖:")
    for package_name, import_name in required_packages:
        if check_package(package_name, import_name):
            print(f"✅ {package_name} - 已安装")
        else:
            print(f"❌ {package_name} - 未安装，正在安装...")
            if install_package(package_name):
                print(f"✅ {package_name} - 安装成功")
            else:
                print(f"❌ {package_name} - 安装失败")
                all_installed = False
    
    print("\n检查可选依赖:")
    for package_name, import_name in optional_packages:
        if check_package(package_name, import_name):
            print(f"✅ {package_name} - 已安装")
        else:
            print(f"⚠️  {package_name} - 未安装（可选）")
    
    print("\n" + "="*50)
    if all_installed:
        print("✅ 所有必需依赖已安装完成!")
        print("现在可以运行 extract_behavior_dataset.py 了")
    else:
        print("❌ 部分依赖安装失败，请手动安装:")
        print("pip install opencv-python numpy tqdm ultralytics Pillow")
    
    print("\n使用说明:")
    print("1. 运行: python extract_behavior_dataset.py")
    print("2. 或直接使用: python behavior_frame_extractor.py [视频路径]")

if __name__ == "__main__":
    main()