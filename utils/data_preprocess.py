import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
import joblib

# 1. 加载数据集
data = pd.read_csv("../data/train.csv")
# 2. 处理时间特征（拆分datetime为小时/星期/月份）
data["datetime"] = pd.to_datetime(data["datetime"])
data["hour"] = data["datetime"].dt.hour
data["weekday"] = data["datetime"].dt.weekday
data["month"] = data["datetime"].dt.month

# 3. 选择模型输入特征（排除无关字段）
features = ["season", "holiday", "workingday", "weather",
            "temp", "atemp", "humidity", "windspeed",
            "hour", "weekday", "month"]
target = "count"

# 4. 归一化（LSTM必需）
scaler_x = MinMaxScaler(feature_range=(0, 1))
scaler_y = MinMaxScaler(feature_range=(0, 1))
x_scaled = scaler_x.fit_transform(data[features])
y_scaled = scaler_y.fit_transform(data[target].values.reshape(-1, 1))

# 5. 构造时序序列（前24小时预测下1小时）
TIME_STEPS = 24
x_seq, y_seq = [], []
for i in range(len(x_scaled) - TIME_STEPS):
    x_seq.append(x_scaled[i:i+TIME_STEPS])
    y_seq.append(y_scaled[i+TIME_STEPS])
x_seq = np.array(x_seq)
y_seq = np.array(y_seq)

# 6. 划分训练集/验证集（按时间顺序，避免数据泄露）
train_size = int(len(x_seq) * 0.8)
x_train, x_val = x_seq[:train_size], x_seq[train_size:]
y_train, y_val = y_seq[:train_size], y_seq[train_size:]

# 7. 保存结果（供模型训练使用）
np.save("../data/x_train.npy", x_train)
np.save("../data/x_val.npy", x_val)
np.save("../data/y_train.npy", y_train)
np.save("../data/y_val.npy", y_val)
joblib.dump(scaler_x, "../utils/scaler_x.pkl")
joblib.dump(scaler_y, "../utils/scaler_y.pkl")

print("✅ 数据预处理+序列构造完成！")
print(f"训练集形状：{x_train.shape}（样本数, 时间步, 特征数）")
print(f"验证集形状：{x_val.shape}")