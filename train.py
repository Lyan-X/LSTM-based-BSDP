import tensorflow as tf
from tensorflow.keras.callbacks import EarlyStopping
import numpy as np
import matplotlib.pyplot as plt
import joblib
from preprocess import preprocess_data
from model import build_lstm_model

# matplotlib中文配置
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

def train_model(data_file, seq_len=6, batch_size=16, epochs=100, patience=5):
    """
    训练LSTM模型
    1. 数据划分：按时间顺序 7:2:1 拆分训练 / 验证 / 测试集（禁止随机打乱）
    2. 训练参数：batch_size=8/16，epoch=100，添加早停（patience=5）
    3. 损失函数：用 MSE（回归任务）
    4. 保存模型：ysu_lstm_bsdp_model.h5
    5. 测试集评估：计算MSE和MAE
    6. 反归一化预测结果：还原真实车辆数
    """
    # 1. 预处理数据
    (X_train, y_train, X_val, y_val, X_test, y_test), scalers = preprocess_data(data_file, seq_len=seq_len)
    input_shape = (X_train.shape[1], X_train.shape[2])
    
    print(f"数据预处理完成")
    print(f"训练集形状：X={X_train.shape}, y={y_train.shape}")
    print(f"验证集形状：X={X_val.shape}, y={y_val.shape}")
    print(f"测试集形状：X={X_test.shape}, y={y_test.shape}")
    
    # 2. 构建模型
    model = build_lstm_model(input_shape)
    model.summary()
    
    # 3. 早停回调（防止过拟合）
    early_stopping = EarlyStopping(monitor="val_loss", patience=patience, restore_best_weights=True)
    
    # 4. 训练模型
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        batch_size=batch_size,
        epochs=epochs,
        callbacks=[early_stopping]
    )
    
    # 5. 保存模型
    model.save("results/ysu_lstm_bsdp_model.h5")
    print("模型已保存到 results/ysu_lstm_bsdp_model.h5")
    
    # 6. 测试集评估
    test_loss, test_mae = model.evaluate(X_test, y_test)
    print(f"测试集MSE损失：{test_loss:.4f}，MAE：{test_mae:.4f}")
    
    # 7. 反归一化预测结果（还原真实车辆数）
    bike_scaler = scalers[0]
    y_pred = model.predict(X_test)
    y_test_original = bike_scaler.inverse_transform(y_test)
    y_pred_original = bike_scaler.inverse_transform(y_pred)
    print(f"真实车辆数示例：{y_test_original[:5].flatten()}")
    print(f"预测车辆数示例：{y_pred_original[:5].flatten()}")
    
    # 8. 可视化训练过程
    plot_training_history(history)
    
    # 9. 可视化预测结果
    plot_prediction_results(y_test_original, y_pred_original)
    
    return model, (y_test_original, y_pred_original)

def plot_training_history(history):
    """
    可视化训练过程
    """
    plt.figure(figsize=(12, 6))
    plt.plot(history.history['loss'], label='训练集损失', color='blue')
    plt.plot(history.history['val_loss'], label='验证集损失', color='red')
    plt.title('LSTM模型训练损失曲线')
    plt.xlabel('Epoch')
    plt.ylabel('MSE Loss')
    plt.legend()
    plt.grid(True)
    plt.savefig('results/training_loss.png')
    plt.close()  # 关闭图形，避免内存占用

def plot_prediction_results(y_test_original, y_pred_original, loc_name="第四体育场"):
    """
    可视化预测结果
    """
    # 取前50个样本可视化
    plt.figure(figsize=(12, 6))
    plt.plot(y_test_original[:50], label="真实车辆数", color="blue")
    plt.plot(y_pred_original[:50], label="预测车辆数", color="red", linestyle="--")
    plt.title(f"{loc_name} 车辆数预测结果")
    plt.xlabel("时间步")
    plt.ylabel("车辆数")
    plt.legend()
    plt.grid(True)
    plt.savefig(f"results/{loc_name}_pred_result.png")
    plt.close()  # 关闭图形，避免内存占用

if __name__ == "__main__":
    # 训练模型
    model, (y_test, y_pred) = train_model(
        data_file="ysu_bike_data.csv",
        seq_len=6,
        batch_size=16,
        epochs=100,
        patience=5
    )
    
    # 计算评估指标
    from sklearn.metrics import mean_squared_error, mean_absolute_error
    mae = mean_absolute_error(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    
    print(f"\n最终评估指标：")
    print(f"MAE: {mae:.4f}")
    print(f"MSE: {mse:.4f}")
    print(f"RMSE: {rmse:.4f}")
