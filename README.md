# BSDP——Bike sharing hourly demand prediction project based on LSTM
基于 LSTM 的共享单车小时级需求预测项目，涵盖数据预处理、LSTM 模型训练、Django Web 预测系统部署的完整流程。技术栈：Python+TensorFlow+Django+Pandas/Numpy。包含可复现代码、环境配置指南、踩坑解决方案，适合机器学习新手入门时间序列预测，也可作为本科毕设参考项目。
Bike sharing hourly demand prediction project based on LSTM, covering the full workflow of data preprocessing, LSTM model training, and Django web prediction system deployment. Tech stack: Python+TensorFlow+Django+Pandas/Numpy. Includes reproducible code, environment setup guide, and troubleshooting solutions. Suitable for ML beginners to get started with time series prediction, and can be used as a reference for undergrad thesis.

# 基于LSTM的共享单车小时级需求预测

## 项目背景
针对共享单车“高峰无车、平峰闲置”的供需失衡问题，构建LSTM模型捕捉骑行量的时间依赖性，实现小时级需求预测，为城市交通资源调度提供技术支撑。

## 技术栈
- 核心框架：Python 3.9 + TensorFlow 2.15
- 数据处理：Pandas 1.5.3、NumPy 1.26.4、Scikit-learn 1.3.2
- 可视化：Matplotlib 3.7.1
- Web部署：Django 4.2.9

## 环境快速搭建
```bash
# 克隆仓库
git clone https://github.com/Lyan-X/LSTM-based-BSDP.git
cd LSTM-based-BSDP

# 创建虚拟环境（无需提交，本地重建）
python -m venv bsdp_env

# 激活环境（Windows）
.\bsdp_env\Scripts\activate

# 安装依赖（一键复现环境）
pip install -r requirements.txt