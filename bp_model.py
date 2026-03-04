"""
BP神经网络模型（任务书要求：实现BP神经网络并优化达到准确率≥75%）
用于共享单车需求预测，与LSTM模型对比
"""
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, BatchNormalization
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
import numpy as np
import matplotlib.pyplot as plt
import time
from preprocess import preprocess_data
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# matplotlib中文配置
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False


def build_bp_model(input_dim):
    """
    构建优化的BP神经网络模型
    输入维度：input_dim（特征数量）
    隐藏层：3层全连接层（128-64-32），BatchNormalization + Dropout正则化
    输出层：回归任务（激活函数linear）
    """
    model = Sequential()
    # 输入层 + 第一隐藏层
    model.add(Dense(128, activation='relu', input_dim=input_dim))
    model.add(BatchNormalization())
    model.add(Dropout(0.3))
    # 第二隐藏层
    model.add(Dense(64, activation='relu'))
    model.add(BatchNormalization())
    model.add(Dropout(0.2))
    # 第三隐藏层
    model.add(Dense(32, activation='relu'))
    model.add(Dropout(0.1))
    # 输出层：回归任务，预测车辆数（归一化后）
    model.add(Dense(1, activation='linear'))

    # 编译模型
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                  loss='mse', metrics=['mae'])
    return model


def train_bp_model(data_file, seq_len=24, batch_size=32, epochs=150, patience=10):
    """
    训练BP神经网络模型
    BP模型不需要时序窗口，将LSTM序列展平为一维特征向量
    """
    start_time = time.time()

    # 1. 预处理数据（复用LSTM的预处理流程）
    (X_train, y_train, X_val, y_val, X_test, y_test), scalers = preprocess_data(data_file, seq_len=seq_len)

    # 2. 将3D序列展平为2D（BP模型不需要时序结构）
    # 原始形状: (samples, seq_len, features) -> (samples, seq_len * features)
    n_train = X_train.shape[0]
    n_val = X_val.shape[0]
    n_test = X_test.shape[0]
    n_features = X_train.shape[1] * X_train.shape[2]

    X_train_flat = X_train.reshape(n_train, n_features)
    X_val_flat = X_val.reshape(n_val, n_features)
    X_test_flat = X_test.reshape(n_test, n_features)

    print(f"BP模型数据预处理完成")
    print(f"训练集形状：X={X_train_flat.shape}, y={y_train.shape}")
    print(f"验证集形状：X={X_val_flat.shape}, y={y_val.shape}")
    print(f"测试集形状：X={X_test_flat.shape}, y={y_test.shape}")

    # 3. 构建模型
    model = build_bp_model(n_features)
    model.summary()

    # 4. 回调函数
    early_stopping = EarlyStopping(monitor='val_loss', patience=patience, restore_best_weights=True)
    reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-6)

    # 5. 训练模型
    history = model.fit(
        X_train_flat, y_train,
        validation_data=(X_val_flat, y_val),
        batch_size=batch_size,
        epochs=epochs,
        callbacks=[early_stopping, reduce_lr],
        verbose=1
    )

    end_time = time.time()
    training_time = end_time - start_time
    print(f"BP模型训练耗时：{training_time:.2f}秒 = {training_time/60:.2f}分钟")

    # 6. 保存模型
    model.save(f"results/ysu_bp_bsdp_model_{seq_len}.h5")
    print(f"BP模型已保存到 results/ysu_bp_bsdp_model_{seq_len}.h5")

    # 7. 测试集评估
    test_loss, test_mae = model.evaluate(X_test_flat, y_test)
    print(f"BP模型测试集MSE损失：{test_loss:.4f}，MAE：{test_mae:.4f}")

    # 8. 反归一化预测结果
    bike_scaler = scalers[0]
    y_pred = model.predict(X_test_flat)
    y_test_original = bike_scaler.inverse_transform(y_test)
    y_pred_original = bike_scaler.inverse_transform(y_pred)

    # 9. 转换为非负整数
    y_test_original = np.round(y_test_original).astype(int)
    y_pred_original = np.round(y_pred_original).astype(int)
    y_pred_original = np.maximum(y_pred_original, 0)

    # 10. 计算评估指标
    mae = mean_absolute_error(y_test_original, y_pred_original)
    mse = mean_squared_error(y_test_original, y_pred_original)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_test_original, y_pred_original) * 100  # 转为百分比

    print(f"\nBP模型最终评估指标：")
    print(f"MAE: {mae:.2f}")
    print(f"RMSE: {rmse:.2f}")
    print(f"R²准确率: {r2:.2f}%")

    # 11. 可视化
    plot_bp_training_history(history, seq_len)
    plot_bp_prediction_results(y_test_original, y_pred_original, seq_len)

    return model, (y_test_original, y_pred_original), training_time, (mae, rmse, r2)


def plot_bp_training_history(history, seq_len):
    """可视化BP模型训练过程"""
    plt.figure(figsize=(12, 6))
    plt.plot(history.history['loss'], label='训练集损失', color='blue')
    plt.plot(history.history['val_loss'], label='验证集损失', color='red')
    plt.title(f'BP神经网络训练损失曲线（{seq_len}小时窗口）')
    plt.xlabel('Epoch')
    plt.ylabel('MSE Loss')
    plt.legend()
    plt.grid(True)
    plt.savefig(f'results/bp_training_loss_{seq_len}.png')
    plt.close()


def plot_bp_prediction_results(y_test_original, y_pred_original, seq_len, loc_name="燕山大学"):
    """可视化BP模型预测结果"""
    plt.figure(figsize=(12, 6))
    plt.plot(y_test_original[:50], label="真实车辆数", color="blue")
    plt.plot(y_pred_original[:50], label="BP预测车辆数", color="orange", linestyle="--")
    plt.title(f"{loc_name} BP神经网络车辆数预测（{seq_len}小时窗口）")
    plt.xlabel("时间步")
    plt.ylabel("车辆数")
    plt.legend()
    plt.grid(True)
    plt.savefig(f"results/bp_{loc_name}_pred_result_{seq_len}.png")
    plt.close()


def compare_lstm_bp(data_file, seq_len=24):
    """LSTM与BP模型对比实验"""
    from train import train_model as train_lstm

    print("=" * 60)
    print("开始LSTM与BP模型对比实验")
    print("=" * 60)

    results = {}

    # 训练LSTM
    print("\n--- 训练LSTM模型 ---")
    try:
        lstm_model, (lstm_y_test, lstm_y_pred), lstm_time, (lstm_mae, lstm_rmse) = train_lstm(
            data_file=data_file, seq_len=seq_len, batch_size=16, epochs=100, patience=5
        )
        lstm_r2 = r2_score(lstm_y_test, lstm_y_pred) * 100
        results['lstm'] = {'mae': lstm_mae, 'rmse': lstm_rmse, 'r2': lstm_r2, 'time': lstm_time}
    except Exception as e:
        print(f"LSTM训练失败: {e}")
        results['lstm'] = None

    # 训练BP
    print("\n--- 训练BP模型 ---")
    try:
        bp_model, (bp_y_test, bp_y_pred), bp_time, (bp_mae, bp_rmse, bp_r2) = train_bp_model(
            data_file=data_file, seq_len=seq_len, batch_size=32, epochs=150, patience=10
        )
        results['bp'] = {'mae': bp_mae, 'rmse': bp_rmse, 'r2': bp_r2, 'time': bp_time}
    except Exception as e:
        print(f"BP训练失败: {e}")
        results['bp'] = None

    # 对比结果
    print("\n" + "=" * 60)
    print("模型对比结果")
    print("=" * 60)
    for model_name, metrics in results.items():
        if metrics:
            print(f"{model_name.upper()}: MAE={metrics['mae']:.2f}, RMSE={metrics['rmse']:.2f}, "
                  f"R²={metrics['r2']:.2f}%, 训练时间={metrics['time']/60:.2f}分钟")

    return results


if __name__ == "__main__":
    import os
    os.makedirs("results", exist_ok=True)

    data_file = "ysu_bike_data.csv"

    # 单独训练BP模型
    print("开始训练BP神经网络模型...")
    bp_model, (y_test, y_pred), training_time, metrics = train_bp_model(
        data_file=data_file,
        seq_len=24,  # 1天窗口
        batch_size=32,
        epochs=150,
        patience=10
    )

    print(f"\nBP模型训练完成！")
    print(f"MAE: {metrics[0]:.2f}, RMSE: {metrics[1]:.2f}, R²: {metrics[2]:.2f}%")
