#!/usr/bin/env python3
"""
依赖安装脚本
自动安装项目所需的所有依赖包
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(command, description=""):
    """运行命令并显示进度"""
    print(f"正在{description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, 
                              capture_output=True, text=True)
        print(f"✓ {description}完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description}失败: {e.stderr}")
        return False

def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("错误: 需要Python 3.8或更高版本")
        return False
    print(f"✓ Python版本: {version.major}.{version.minor}.{version.micro}")
    return True

def install_pytorch():
    """安装PyTorch"""
    print("检测CUDA支持...")
    
    # 检查是否有NVIDIA GPU
    try:
        result = subprocess.run("nvidia-smi", shell=True, capture_output=True)
        has_gpu = result.returncode == 0
    except:
        has_gpu = False
    
    if has_gpu:
        print("检测到NVIDIA GPU，安装CUDA版本的PyTorch...")
        torch_command = "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118"
    else:
        print("未检测到NVIDIA GPU，安装CPU版本的PyTorch...")
        torch_command = "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu"
    
    return run_command(torch_command, "安装PyTorch")

def install_requirements():
    """安装requirements.txt中的依赖"""
    requirements_path = Path(__file__).parent.parent / "requirements.txt"
    
    if not requirements_path.exists():
        print("错误: requirements.txt文件不存在")
        return False
    
    # 先升级pip
    run_command("pip install --upgrade pip", "升级pip")
    
    # 安装PyTorch (单独安装以确保正确版本)
    if not install_pytorch():
        return False
    
    # 安装其他依赖
    command = f"pip install -r {requirements_path}"
    return run_command(command, "安装项目依赖")

def verify_installation():
    """验证安装是否成功"""
    print("\n验证安装...")
    
    packages_to_check = [
        "torch",
        "ultralytics", 
        "opencv-python",
        "numpy",
        "matplotlib",
        "streamlit"
    ]
    
    all_installed = True
    for package in packages_to_check:
        try:
            __import__(package.replace("-", "_"))
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} 未正确安装")
            all_installed = False
    
    return all_installed

def create_virtual_env():
    """创建虚拟环境（可选）"""
    response = input("是否创建虚拟环境？(y/n): ").lower().strip()
    if response == 'y':
        env_name = "lab_safety_env"
        print(f"创建虚拟环境: {env_name}")
        
        if run_command(f"python3 -m venv {env_name}", "创建虚拟环境"):
            print(f"虚拟环境已创建: {env_name}")
            print(f"激活命令: source {env_name}/bin/activate")
            return True
    return False

def main():
    """主函数"""
    print("==================================================")
    print("实验室安全检测系统 - 依赖安装")
    print("==================================================\n")
    
    # 检查Python版本
    if not check_python_version():
        sys.exit(1)
    
    # 询问是否创建虚拟环境
    create_virtual_env()
    
    # 安装依赖
    print("\n开始安装依赖包...")
    if not install_requirements():
        print("依赖安装失败，请检查错误信息")
        sys.exit(1)
    
    # 验证安装
    if verify_installation():
        print("\n✓ 所有依赖安装成功！")
        print("\n下一步:")
        print("1. 准备训练数据: python3 src/data_preparation.py")
        print("2. 开始训练模型: python3 src/train_model.py")
        print("3. 启动Web应用: streamlit run src/web_app.py")
    else:
        print("\n⚠️  部分依赖安装失败，请手动检查")
        sys.exit(1)

if __name__ == "__main__":
    main()