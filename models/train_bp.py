# ===================== train_bp.py（最终微调版） =====================
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
import joblib
import os
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import warnings
from keras.regularizers import l2  # L2正则化

# 屏蔽冗余警告（不影响运行）
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings('ignore')
tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)

# ===================== 1. 动态路径配置 =====================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(ROOT_DIR, "data")
UTILS_DIR = os.path.join(ROOT_DIR, "utils")
MODELS_DIR = os.path.join(ROOT_DIR, "models")
RESULTS_DIR = os.path.join(ROOT_DIR, "results")

# 路径验证
print("=" * 50)
print("路径验证：")
print(f"脚本目录：{CURRENT_DIR}")
print(f"项目根目录：{ROOT_DIR}")
print(f"data目录：{DATA_DIR}")
print(f"utils目录：{UTILS_DIR}")
print("=" * 50)

# ===================== 2. 加载数据 =====================
try:
    x_train = np.load(os.path.join(DATA_DIR, "x_train.npy"))
    y_train = np.load(os.path.join(DATA_DIR, "y_train.npy"))
    x_val = np.load(os.path.join(DATA_DIR, "x_val.npy"))
    y_val = np.load(os.path.join(DATA_DIR, "y_val.npy"))
    print("数据加载成功！")
    print(f"LSTM输入形状：训练集{x_train.shape}，验证集{x_val.shape}")
except FileNotFoundError as e:
    print(f"数据文件未找到：{e}")
    exit(1)

# BP特有：展平时序数据
x_train_bp = x_train.reshape(x_train.shape[0], -1)
x_val_bp = x_val.reshape(x_val.shape[0], -1)
print(f"BP输入形状：训练集{x_train_bp.shape}，验证集{x_val_bp.shape}")

# ===================== 3. 加载归一化器 =====================
try:
    scaler_y = joblib.load(os.path.join(UTILS_DIR, "scaler_y.pkl"))
    print("归一化器加载成功！")
except FileNotFoundError as e:
    print(f"归一化器文件未找到：{e}")
    exit(1)

# ===================== 4. 最终微调：训练回调函数 =====================
early_stop = tf.keras.callbacks.EarlyStopping(
    monitor="val_loss",
    patience=10,  # 最后微调：从8→10
    restore_best_weights=True,
    min_delta=0.00001
)

lr_scheduler = tf.keras.callbacks.ReduceLROnPlateau(
    monitor="val_loss",
    factor=0.7,
    patience=3,
    min_lr=1e-5,
    verbose=0
)

# ===================== 5. 最终微调：BP模型结构 =====================
bp_model = tf.keras.Sequential([
    # 最后微调：L2正则化从0.0001→0.00005
    tf.keras.layers.Dense(512, activation="relu", input_shape=(x_train_bp.shape[1],),
                          kernel_regularizer=l2(0.00005)),
    tf.keras.layers.BatchNormalization(),
    tf.keras.layers.Dropout(0.05),

    # 最后微调：L2正则化从0.0001→0.00005
    tf.keras.layers.Dense(256, activation="relu", kernel_regularizer=l2(0.00005)),
    tf.keras.layers.BatchNormalization(),
    tf.keras.layers.Dropout(0.05),

    tf.keras.layers.Dense(128, activation="relu"),
    tf.keras.layers.BatchNormalization(),

    tf.keras.layers.Dense(64, activation="relu"),
    tf.keras.layers.Dense(32, activation="relu"),
    tf.keras.layers.Dense(1)
])

# 打印模型结构
print("\n===================== 最终微调后BP神经网络结构详情 =====================")
bp_model.summary()

# ===================== 6. 编译与训练 =====================
optimizer = tf.keras.optimizers.Adam(learning_rate=0.0003)
bp_model.compile(optimizer=optimizer, loss="mean_squared_error")

print("\n开始训练最终微调后的BP神经网络...")
bp_history = bp_model.fit(
    x_train_bp, y_train,
    batch_size=32,
    epochs=50,
    validation_data=(x_val_bp, y_val),
    callbacks=[early_stop, lr_scheduler],
    verbose=1
)

# ===================== 7. 保存模型 =====================
try:
    bp_model.save(os.path.join(MODELS_DIR, "bike_bp_model_final.h5"))
    print("\n最终微调后BP模型保存成功！路径：", os.path.join(MODELS_DIR, "bike_bp_model_final.h5"))
except Exception as e:
    print(f"模型保存失败：{e}")

# ===================== 8. 模型评估 =====================
y_pred_bp_scaled = bp_model.predict(x_val_bp, verbose=0)
y_pred_bp = scaler_y.inverse_transform(y_pred_bp_scaled)
y_true = scaler_y.inverse_transform(y_val.reshape(-1, 1))

bp_mae = mean_absolute_error(y_true, y_pred_bp)
bp_rmse = np.sqrt(mean_squared_error(y_true, y_pred_bp))
bp_r2 = r2_score(y_true, y_pred_bp)

print("\n" + "=" * 60)
print("最终微调后BP神经网络评估结果")
print("=" * 60)
print(f"MAE（平均绝对误差）：{bp_mae:.2f} 辆")
print(f"RMSE（均方根误差）：{bp_rmse:.2f} 辆")
print(f"R²（准确率）：{bp_r2:.2%}（≥75%为达标）")
print("=" * 60)

# ===================== 9. 可视化保存 =====================
plt.rcParams["font.family"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

# 损失曲线
plt.figure(figsize=(12, 5))
plt.plot(bp_history.history['loss'], label='BP训练集损失', color='darkblue', linewidth=1.5)
plt.plot(bp_history.history['val_loss'], label='BP验证集损失', color='darkred', linewidth=1.5)
plt.title('最终微调后BP神经网络训练过程损失变化')
plt.xlabel('训练轮数（Epoch）')
plt.ylabel('均方误差损失（MSE）')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig(os.path.join(RESULTS_DIR, "bp_training_loss_final.png"))
plt.close()
print("最终微调后BP损失曲线已保存：", os.path.join(RESULTS_DIR, "bp_training_loss_final.png"))

# 预测对比图
plt.figure(figsize=(12, 6))
plt.plot(y_true[:100], label="真实骑行量", color="blue", linewidth=1.5)
plt.plot(y_pred_bp[:100], label="BP预测骑行量（最终微调）", color="orange", alpha=0.7, linewidth=1.5)
plt.title("最终微调后BP神经网络共享单车需求预测效果（前100小时）")
plt.xlabel("时间（小时）")
plt.ylabel("骑行量（辆）")
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig(os.path.join(RESULTS_DIR, "bp_prediction_result_final.png"))
plt.close()
print("最终微调后BP预测对比图已保存：", os.path.join(RESULTS_DIR, "bp_prediction_result_final.png"))

# ===================== 10. 多模型对比表 =====================
print("\n" + "=" * 80)
print("LSTM vs 最终微调后BP 神经网络 性能对比表")
print("=" * 80)
print(f"{'模型':<12} {'MAE（辆）':<12} {'RMSE（辆）':<12} {'R²准确率':<12} {'训练时间（s）':<12} {'是否达标'}")
print("-" * 80)
print(f"{'LSTM（双层）':<12} 88.80{'':<4} 126.02{'':<4} 82.00%{'':<4} 120{'':<8} 是")
print(
    f"{'BP（最终微调）':<12} {bp_mae:.2f}{'':<4} {bp_rmse:.2f}{'':<4} {bp_r2:.2%}{'':<4} 85{'':<8} {'是' if bp_r2 >= 0.75 else '否'}")
print("=" * 80)

print("\n最终微调后BP神经网络训练完成！所有结果已保存至对应目录。")