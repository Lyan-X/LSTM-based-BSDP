import tensorflow as tf
from tensorflow.keras.callbacks import EarlyStopping
import numpy as np
import matplotlib.pyplot as plt
import joblib
import time
from preprocess import preprocess_data
from model import build_lstm_model

# matplotlib中文配置
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

def train_model(data_file, seq_len=336, batch_size=16, epochs=100, patience=5):
    """
    训练LSTM模型
    1. 数据划分：按时间顺序 7:2:1 拆分训练 / 验证 / 测试集（禁止随机打乱）
    2. 训练参数：batch_size=8/16/32，epoch=100，添加早停（patience=5）
    3. 损失函数：用 MSE（回归任务）
    4. 保存模型：ysu_lstm_bsdp_model.h5
    5. 测试集评估：计算MSE和MAE
    6. 反归一化预测结果：还原真实车辆数并转换为非负整数
    """
    # 记录训练开始时间
    start_time = time.time()
    
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
    
    # 记录训练结束时间
    end_time = time.time()
    training_time = end_time - start_time
    print(f"训练耗时：{training_time:.2f}秒 = {training_time/60:.2f}分钟")
    
    # 5. 保存模型
    model.save(f"results/ysu_lstm_bsdp_model_{seq_len}.h5")
    print(f"模型已保存到 results/ysu_lstm_bsdp_model_{seq_len}.h5")
    
    # 6. 测试集评估
    test_loss, test_mae = model.evaluate(X_test, y_test)
    print(f"测试集MSE损失：{test_loss:.4f}，MAE：{test_mae:.4f}")
    
    # 7. 反归一化预测结果（还原真实车辆数）
    bike_scaler = scalers[0]
    y_pred = model.predict(X_test)
    y_test_original = bike_scaler.inverse_transform(y_test)
    y_pred_original = bike_scaler.inverse_transform(y_pred)
    
    # 8. 转换为非负整数
    y_test_original = np.round(y_test_original).astype(int)
    y_pred_original = np.round(y_pred_original).astype(int)
    y_pred_original = np.maximum(y_pred_original, 0)  # 确保非负
    
    print(f"真实车辆数示例：{y_test_original[:5].flatten()}")
    print(f"预测车辆数示例：{y_pred_original[:5].flatten()}")
    
    # 9. 可视化训练过程
    plot_training_history(history, seq_len)
    
    # 10. 可视化预测结果
    plot_prediction_results(y_test_original, y_pred_original, seq_len)
    
    # 11. 计算评估指标
    from sklearn.metrics import mean_squared_error, mean_absolute_error
    mae = mean_absolute_error(y_test_original, y_pred_original)
    mse = mean_squared_error(y_test_original, y_pred_original)
    rmse = np.sqrt(mse)
    
    print(f"\n最终评估指标：")
    print(f"MAE: {mae:.2f}")
    print(f"RMSE: {rmse:.2f}")
    
    return model, (y_test_original, y_pred_original), training_time, (mae, rmse)

def plot_training_history(history, seq_len):
    """
    可视化训练过程
    """
    plt.figure(figsize=(12, 6))
    plt.plot(history.history['loss'], label='训练集损失', color='blue')
    plt.plot(history.history['val_loss'], label='验证集损失', color='red')
    plt.title(f'LSTM模型训练损失曲线（{seq_len}小时）')
    plt.xlabel('Epoch')
    plt.ylabel('MSE Loss')
    plt.legend()
    plt.grid(True)
    plt.savefig(f'results/training_loss_{seq_len}.png')
    plt.close()  # 关闭图形，避免内存占用

def plot_prediction_results(y_test_original, y_pred_original, seq_len, loc_name="第四体育场"):
    """
    可视化预测结果
    """
    # 取前50个样本可视化
    plt.figure(figsize=(12, 6))
    plt.plot(y_test_original[:50], label="真实车辆数", color="blue")
    plt.plot(y_pred_original[:50], label="预测车辆数", color="red", linestyle="--")
    plt.title(f"{loc_name} 车辆数预测结果（{seq_len}小时）")
    plt.xlabel("时间步")
    plt.ylabel("车辆数")
    plt.legend()
    plt.grid(True)
    plt.savefig(f"results/{loc_name}_pred_result_{seq_len}.png")
    plt.close()  # 关闭图形，避免内存占用

def plot_comparison_results(results):
    """
    可视化不同数据量的对比结果
    """
    seq_lens = []
    training_times = []
    maes = []
    rmses = []
    
    for result in results:
        seq_len, training_time, mae, rmse = result
        seq_lens.append(seq_len)
        training_times.append(training_time/60)  # 转换为分钟
        maes.append(mae)
        rmses.append(rmse)
    
    # 绘制精度-耗时对比图
    plt.figure(figsize=(12, 6))
    
    # 精度指标
    ax1 = plt.gca()
    ax1.plot(seq_lens, maes, label='MAE', color='blue', marker='o')
    ax1.plot(seq_lens, rmses, label='RMSE', color='green', marker='s')
    ax1.set_xlabel('时间窗口（小时）')
    ax1.set_ylabel('误差', color='blue')
    ax1.tick_params(axis='y', labelcolor='blue')
    ax1.legend(loc='upper left')
    
    # 训练时间
    ax2 = ax1.twinx()
    ax2.plot(seq_lens, training_times, label='训练时间（分钟）', color='red', marker='^')
    ax2.set_ylabel('训练时间（分钟）', color='red')
    ax2.tick_params(axis='y', labelcolor='red')
    ax2.legend(loc='upper right')
    
    plt.title('不同时间窗口的精度-耗时对比')
    plt.grid(True)
    plt.savefig('results/comparison_results.png')
    plt.close()

if __name__ == "__main__":
    # 对比实验：不同时间窗口
    data_file = "ysu_bike_data.csv"
    results = []
    
    # 首先检查数据量
    import pandas as pd
    df = pd.read_csv(data_file)
    print(f"原始数据量: {len(df)} 条")
    print(f"时间范围: {df['timestamp'].min()} 到 {df['timestamp'].max()}")
    print(f"停车点数量: {df['location_name'].nunique()} 个")
    
    # 使用原始的时间窗口设置
    time_windows = [168, 336, 720]  # 7天、14天、30天
    batch_sizes = [8, 16, 32]
    
    for i, seq_len in enumerate(time_windows):
        print(f"\n===== 训练 {seq_len//24}天（{seq_len}小时） 模型 =====")
        try:
            model, (y_test, y_pred), training_time, metrics = train_model(
                data_file=data_file,
                seq_len=seq_len,
                batch_size=batch_sizes[i],
                epochs=100,
                patience=5
            )
            results.append((seq_len, training_time, metrics[0], metrics[1]))
        except Exception as e:
            print(f"训练失败: {e}")
            continue
    
    # 绘制对比结果
    plot_comparison_results(results)
    
    # 输出对比结论
    print("\n===== 对比实验结论 =====")
    for result in results:
        seq_len, training_time, mae, rmse = result
        days = seq_len // 24
        print(f"{days}天数据：训练耗时={training_time/60:.2f}分钟, MAE={mae:.2f}, RMSE={rmse:.2f}")
    
    # 分析最优解
    best_result = min(results, key=lambda x: x[2])  # 按MAE排序
    best_days = best_result[0] // 24
    print(f"\n最优解：{best_days}天数据，MAE={best_result[2]:.2f}")
