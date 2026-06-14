#!/usr/bin/env python3
"""
设置实验环境脚本
创建独立的Python虚拟环境并安装所需依赖
"""

import os
import sys
import subprocess

# 日志函数
def log(message):
    print(f"[INFO] {message}")

# 创建虚拟环境
def create_venv():
    venv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv')
    
    if not os.path.exists(venv_dir):
        log("创建虚拟环境...")
        try:
            subprocess.run([sys.executable, '-m', 'venv', venv_dir], check=True)
            log("虚拟环境创建成功")
        except Exception as e:
            log(f"创建虚拟环境失败: {e}")
            return False
    else:
        log("虚拟环境已存在")
    
    return True

# 安装依赖
def install_dependencies():
    venv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv')
    
    # 确定pip路径
    if sys.platform == 'win32':
        pip_path = os.path.join(venv_dir, 'Scripts', 'pip.exe')
    else:
        pip_path = os.path.join(venv_dir, 'bin', 'pip')
    
    # 依赖列表
    dependencies = [
        'kagglehub',
        'pandas',
        'scikit-learn',
        'tensorflow',
        'numpy'
    ]
    
    log("安装依赖...")
    try:
        for dep in dependencies:
            subprocess.run([pip_path, 'install', dep], check=True)
        log("依赖安装成功")
        return True
    except Exception as e:
        log(f"安装依赖失败: {e}")
        return False

# 验证环境
def verify_env():
    venv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv')
    
    # 确定python路径
    if sys.platform == 'win32':
        python_path = os.path.join(venv_dir, 'Scripts', 'python.exe')
    else:
        python_path = os.path.join(venv_dir, 'bin', 'python')
    
    log("验证环境...")
    try:
        # 检查Python版本
        result = subprocess.run([python_path, '--version'], capture_output=True, text=True)
        log(f"Python版本: {result.stdout.strip()}")
        
        # 检查依赖是否安装
        result = subprocess.run([python_path, '-c', 'import kagglehub; import pandas; import sklearn; import tensorflow; import numpy; print(\"All dependencies installed successfully\")'], 
                              capture_output=True, text=True)
        log(result.stdout.strip())
        
        if result.returncode == 0:
            log("环境验证成功")
            return True
        else:
            log(f"环境验证失败: {result.stderr}")
            return False
    except Exception as e:
        log(f"验证环境失败: {e}")
        return False

# 主函数
def main():
    log("开始设置实验环境...")
    
    # 创建虚拟环境
    if not create_venv():
        log("无法创建虚拟环境，退出")
        return 1
    
    # 安装依赖
    if not install_dependencies():
        log("无法安装依赖，退出")
        return 1
    
    # 验证环境
    if not verify_env():
        log("环境验证失败，退出")
        return 1
    
    log("环境设置完成！")
    log("使用以下命令运行实验:")
    venv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv')
    if sys.platform == 'win32':
        python_path = os.path.join(venv_dir, 'Scripts', 'python.exe')
    else:
        python_path = os.path.join(venv_dir, 'bin', 'python')
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bike_demand_prediction.py')
    log(f"{python_path} {script_path}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())