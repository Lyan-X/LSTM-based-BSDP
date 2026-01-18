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

项目运行流程
数据预处理：执行utils/data_preprocess.py（处理原始数据集，构造 24 小时时序窗口）；
模型训练：执行models/train_lstm.py（双层 LSTM+Dropout，早停机制防止过拟合）；
Web 部署：进入web/目录，执行python manage.py runserver（可视化预测界面）。

实验结果
验证集 平均绝对误差（MAE）：91.14 辆，均方根误差（RMSE）：129.24 辆；
模型可有效捕捉早高峰（7-9 点）、晚高峰（17-19 点）的骑行量峰值。

数据集来源
UCI Bike Sharing Demand——Forecast use of a city bikeshare system：https://www.kaggle.com/c/bike-sharing-demand/data?select=train.csv