import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
import joblib
from sklearn.metrics import mean_absolute_error, mean_squared_error

# ===================== 屏蔽冗余警告 =====================
import os
import warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings('ignore')
tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)

# ===================== 1. 加载预处理后的时序数据（修复路径！） =====================
# 路径改为 ./data/（BSDP根目录下的data文件夹）
x_train = np.load("./data/x_train.npy")
y_train = np.load("./data/y_train.npy")
x_val = np.load("./data/x_val.npy")
y_val = np.load("./data/y_val.npy")

# ===================== 2. 搭建LSTM模型 =====================
model = tf.keras.Sequential([
    tf.keras.layers.LSTM(64, return_sequences=True, input_shape=(24, 11)),
    tf.keras.layers.Dropout(0.2),
    tf.keras.layers.LSTM(32, return_sequences=False),
    tf.keras.layers.Dropout(0.2),
    tf.keras.layers.Dense(16, activation="relu"),
    tf.keras.layers.Dense(1)
])

# ===================== 3. LSTM模型结构详情 =====================
print("===================== LSTM模型结构详情 =====================")
model.summary()

# 新增：生成神经网络横向结构图（高清PNG）
try:
    from tensorflow.keras.utils import plot_model
    plot_model(
        model,
        to_file="./results/lstm_model_structure_horizontal.png",  # 横向图单独命名
        show_shapes=True,    # 显示输入/输出维度（关键，便于核对结构）
        show_layer_names=True,  # 显示层名称
        rankdir="LR",  # 核心修改：LR=Left to Right（横向布局），替代原TB（纵向）
        dpi=300  # 高清分辨率
    )
    print("神经网络横向结构图已保存到 results/lstm_model_structure_horizontal.png")
except Exception as e:
    print(f"若要生成结构图，需安装依赖：pip install pydot==1.4.2 graphviz==0.20.1，错误详情：{e}")

# ===================== 4. 编译模型 =====================
model.compile(optimizer="adam", loss="mean_squared_error")

# ===================== 5. 训练模型（加早停避免过拟合） =====================
early_stop = tf.keras.callbacks.EarlyStopping(
    monitor="val_loss",
    patience=3,
    restore_best_weights=True
)
history = model.fit(
    x_train, y_train,
    batch_size=32,
    epochs=20,
    validation_data=(x_val, y_val),
    callbacks=[early_stop]
)

# ===================== 6. 保存训练好的模型 =====================
model.save("./models/bike_lstm_model.h5")
print("模型已保存到 models/bike_lstm_model.h5")

# ===================== 7. 训练损失曲线可视化 =====================
plt.rcParams["font.family"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.figure(figsize=(12, 5))
plt.plot(history.history['loss'], label='训练集损失', color='darkorange', linewidth=1.5)
plt.plot(history.history['val_loss'], label='验证集损失', color='forestgreen', linewidth=1.5)
plt.title('LSTM模型训练过程损失变化')
plt.xlabel('训练轮数（Epoch）')
plt.ylabel('均方误差损失（MSE）')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig("./results/lstm_training_loss.png")
plt.show()
print("训练损失曲线已保存到 results/lstm_training_loss.png")

# ===================== 8. 模型评估与可视化（修复utils路径！） =====================
scaler_y = joblib.load("./utils/scaler_y.pkl")
y_pred_scaled = model.predict(x_val)
y_pred = scaler_y.inverse_transform(y_pred_scaled)
y_true = scaler_y.inverse_transform(y_val.reshape(-1, 1))

mae = mean_absolute_error(y_true, y_pred)
rmse = np.sqrt(mean_squared_error(y_true, y_pred))
print("\n模型预测效果：")
print(f"平均绝对误差：{mae:.2f} 辆")
print(f"均方根误差：{rmse:.2f} 辆")

plt.figure(figsize=(12, 6))
plt.plot(y_true[:100], label="真实骑行量", color="blue", linewidth=1.5)
plt.plot(y_pred[:100], label="预测骑行量", color="red", alpha=0.7, linewidth=1.5)
plt.title("LSTM模型共享单车需求预测效果（前100小时）")
plt.xlabel("时间（小时）")
plt.ylabel("骑行量（辆）")
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig("./results/lstm_prediction_result.png")
plt.show()

print("\n模型训练完成！预测对比图已保存到 results/lstm_prediction_result.png")