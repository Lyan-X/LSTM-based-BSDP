import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
import joblib
from sklearn.metrics import mean_absolute_error, mean_squared_error

# ===================== 1. 加载预处理后的时序数据 =====================
# 数据形状：(样本数, 24时间步, 11特征)，对应24小时数据预测下1小时骑行量
x_train = np.load("../data/x_train.npy")
y_train = np.load("../data/y_train.npy")
x_val = np.load("../data/x_val.npy")
y_val = np.load("../data/y_val.npy")

#  ===================== 2. 搭建LSTM模型 =====================
# 简单的双层LSTM结构，适合共享单车需求预测的时序数据
model = tf.keras.Sequential([
    # 第一层LSTM，64个神经元，输入为24小时的11个特征
    tf.keras.layers.LSTM(64, return_sequences=True, input_shape=(24, 11)),
    tf.keras.layers.Dropout(0.2),  # 防止模型过拟合
    # 第二层LSTM，32个神经元
    tf.keras.layers.LSTM(32, return_sequences=False),
    tf.keras.layers.Dropout(0.2),
    # 全连接层，提升模型拟合能力
    tf.keras.layers.Dense(16, activation="relu"),
    # 输出层：预测骑行量的数值
    tf.keras.layers.Dense(1)
])

# ===================== 3. 编译模型 =====================
# 回归任务用均方误差作为损失函数，Adam优化器调整参数
model.compile(optimizer="adam", loss="mean_squared_error")

#  ===================== 4. 训练模型（加早停避免过拟合） =====================
# 早停设置：验证集效果3轮没提升就停止，避免训练过度
early_stop = tf.keras.callbacks.EarlyStopping(
    monitor="val_loss",
    patience=3,
    restore_best_weights=True
)

# 开始训练模型
history = model.fit(
    x_train, y_train,
    batch_size=32,
    epochs=20,
    validation_data=(x_val, y_val),
    callbacks=[early_stop]
)

# ===================== 5. 保存训练好的模型 =====================
# 保存为h5格式，供后续Django Web系统调用
model.save("../models/bike_lstm_model.h5")
print("模型已保存到 models/bike_lstm_model.h5")

# ===================== 6. 模型评估与可视化 =====================
# 加载归一化器，把预测值还原成真实的骑行量数值
scaler_y = joblib.load("../utils/scaler_y.pkl")
y_pred_scaled = model.predict(x_val)
y_pred = scaler_y.inverse_transform(y_pred_scaled)
y_true = scaler_y.inverse_transform(y_val)

# 计算预测误差
mae = mean_absolute_error(y_true, y_pred)
rmse = np.sqrt(mean_squared_error(y_true, y_pred))
print("\n模型预测效果：")
print(f"平均绝对误差：{mae:.2f} 辆")
print(f"均方根误差：{rmse:.2f} 辆")

# 解决中文显示问题
plt.rcParams["font.family"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

# 绘制预测结果对比图
plt.figure(figsize=(12, 6))
plt.plot(y_true[:100], label="真实骑行量", color="blue", linewidth=1.5)
plt.plot(y_pred[:100], label="预测骑行量", color="red", alpha=0.7, linewidth=1.5)
# 坐标轴标注（带明确单位）
plt.title("LSTM模型共享单车需求预测效果（前100小时）")
plt.xlabel("时间（小时）")
plt.ylabel("骑行量（辆）")
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig("../results/prediction_result.png")
plt.show()

print("\n模型训练完成！预测对比图已保存到 results/prediction_result.png")